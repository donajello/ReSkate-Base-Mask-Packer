# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from bpy.props import PointerProperty, IntProperty, BoolProperty, StringProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bl_operators.presets import AddPresetBase
import numpy as np
import struct, zlib
from pathlib import Path

CHANNELS=[('R','Red','Read the source red channel'),('G','Green','Read the source green channel'),('B','Blue','Read the source blue channel'),('A','Alpha','Read the source alpha channel'),('L','Luminance','Calculate a weighted grayscale value from RGB')]

def sample(image, channel, w, h, nearest=False):
    sw,sh=image.size
    if not sw or not sh: raise ValueError('Input image is empty: '+image.name)
    if image.channels != 4: raise ValueError('Input must expose RGBA pixels: '+image.name)
    pixels=np.empty(sw*sh*4,np.float32);image.pixels.foreach_get(pixels)
    a=pixels.reshape(sh,sw,4)
    a=(a[:,:,:3]@np.array([.2126,.7152,.0722],np.float32)) if channel=='L' else a[:,:,{'R':0,'G':1,'B':2,'A':3}[channel]]
    if (sw,sh)==(w,h):return np.clip(a,0,1)
    xs=(np.arange(w)+.5)*sw/w-.5;ys=(np.arange(h)+.5)*sh/h-.5
    if nearest:return np.clip(a[np.clip(np.rint(ys).astype(int),0,sh-1)[:,None],np.clip(np.rint(xs).astype(int),0,sw-1)[None,:]],0,1)
    xs=np.clip(xs,0,sw-1);ys=np.clip(ys,0,sh-1);x0=xs.astype(int);y0=ys.astype(int);x1=np.minimum(x0+1,sw-1);y1=np.minimum(y0+1,sh-1);fx=xs-x0;fy=ys-y0
    return np.clip((a[y0[:,None],x0]*(1-fx)+a[y0[:,None],x1]*fx)*(1-fy[:,None])+(a[y1[:,None],x0]*(1-fx)+a[y1[:,None],x1]*fx)*fy[:,None],0,1)

def build_pixels(s):
    values=[]
    for key,constant in [('metal',s.metal_value),('rough',s.rough_value),('section',s.section_value)]:
        image=getattr(s,key+'_image')
        a=sample(image,getattr(s,key+'_channel'),s.width,s.height,key=='section') if image else np.full((s.height,s.width),int(constant)/255,np.float32)
        if key=='rough' and not s.input_smoothness:a=1-a
        if key=='section' and s.snap_sections:a=np.where(a<64/255,0,np.where(a<192/255,128/255,1))
        values.append(a)
    return np.rint(np.clip(np.stack((*values,np.ones_like(values[0])),axis=2),0,1)*255).astype(np.uint8)

def image_pixels(image):
    a=np.empty(image.size[0]*image.size[1]*4,np.float32);image.pixels.foreach_get(a)
    return np.rint(np.clip(a.reshape(image.size[1],image.size[0],4),0,1)*255).astype(np.uint8)

def png_write(path,a):
    # Input arrays follow Blender's bottom-up pixel convention.
    def chunk(tag,data):return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    raw=b''.join(b'\x00'+row.tobytes() for row in a[::-1])
    data=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',a.shape[1],a.shape[0],8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
    Path(path).write_bytes(data)

def bc1_encode(rgb):
    h,w,_=rgb.shape;pad=np.pad(rgb,((0,(-h)%4),(0,(-w)%4),(0,0)),mode='edge')
    blocks=pad.reshape(pad.shape[0]//4,4,pad.shape[1]//4,4,3).transpose(0,2,1,3,4).reshape(-1,16,3)
    output=[]
    for start in range(0,len(blocks),8192):
        v=blocks[start:start+8192].astype(np.int32)
        lo=v.min(1);hi=v.max(1);direction=hi-lo;score=(v*direction[:,None,:]).sum(2)
        n=np.arange(len(v));c0=v[n,score.argmax(1)];c1=v[n,score.argmin(1)]
        def pack(c):return ((np.rint(c[:,0]*31/255).astype(np.uint16)<<11)|(np.rint(c[:,1]*63/255).astype(np.uint16)<<5)|np.rint(c[:,2]*31/255).astype(np.uint16))
        q0=pack(c0);q1=pack(c1);q0,q1=np.maximum(q0,q1),np.minimum(q0,q1)
        def unpack(q):
            r=(q>>11).astype(np.int32);g=((q>>5)&63).astype(np.int32);b=(q&31).astype(np.int32)
            return np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),1)
        p0=unpack(q0);p1=unpack(q1);pal=np.stack((p0,p1,(2*p0+p1)//3,(p0+2*p1)//3),1)
        dist=((v[:,:,None,:]-pal[:,None,:,:])**2).sum(3);idx=dist.argmin(2).astype(np.uint32)
        # Equal endpoints use BC1's three-color mode. Force endpoint index 0 for opaque solids.
        idx[q0==q1]=0
        bits=np.bitwise_or.reduce(idx<<np.arange(0,32,2,dtype=np.uint32),axis=1)
        encoded=np.empty(len(v),dtype=[('a','<u2'),('b','<u2'),('i','<u4')]);encoded['a']=q0;encoded['b']=q1;encoded['i']=bits;output.append(encoded.tobytes())
    return b''.join(output)

def dds_write(path,a):
    current=a[::-1,:,:3].copy();chunks=[]
    while True:
        chunks.append(bc1_encode(current));h,w=current.shape[:2]
        if (w,h)==(1,1):break
        ph=np.pad(current,((0,h%2),(0,w%2),(0,0)),mode='edge').astype(np.uint16)
        current=np.rint((ph[0::2,0::2]+ph[1::2,0::2]+ph[0::2,1::2]+ph[1::2,1::2])/4).astype(np.uint8)
    header=struct.pack('<7I',124,0xa1007,a.shape[0],a.shape[1],len(chunks[0]),0,len(chunks))+struct.pack('<11I',*([0]*11))+struct.pack('<8I',32,4,int.from_bytes(b'DX10','little'),0,0,0,0,0)+struct.pack('<5I',0x401008,0,0,0,0)
    Path(path).write_bytes(b'DDS '+header+struct.pack('<5I',71,3,0,1,3)+b''.join(chunks))

class RSM_Settings(bpy.types.PropertyGroup):
    unpack_image:PointerProperty(name='Base mask',type=bpy.types.Image,description='Existing Non-Color base mask to separate into grayscale channel maps')
    unpack_smoothness:BoolProperty(name='Export Smoothness Map',default=False,description='Also create and export a standalone smoothness map. Off by default: only the roughness version is created. Packed base masks still store smoothness in green')
    unpack_export:BoolProperty(name='Export PNG layers',default=False,description='Save every extracted layer to the selected folder as well as creating Blender images; existing filenames are protected')
    unpack_folder:StringProperty(name='Folder',subtype='DIR_PATH',description='Existing folder for unpacked PNG files; select an empty folder to avoid filename conflicts')
    unpack_repack:BoolProperty(name='Use layers as inputs',default=False,description='Populate the packing inputs with extracted metallic, roughness and selector maps; preserve blue values without snapping')
    metal_image:PointerProperty(name='Metallic image',type=bpy.types.Image,description='Metallic data source; reads red by default. Leave empty to use the constant value')
    rough_image:PointerProperty(name='Surface image',type=bpy.types.Image,description='Roughness or smoothness data source; reads green by default. Enable My texture is a smoothness map only when the source is smoothness or glossiness')
    section_image:PointerProperty(name='Section image',type=bpy.types.Image,description='Clothing section selector source; reads blue by default. Leave empty to give the whole item one section')
    output_image:PointerProperty(name='Generated mask',type=bpy.types.Image,description='Generated image used for preview and export. Generate again after changing inputs')
    metal_channel:EnumProperty(name='Source channel',items=CHANNELS,default='R',description='Channel to read from the metallic image; output is always red')
    rough_channel:EnumProperty(name='Source channel',items=CHANNELS,default='G',description='Channel to read from the surface image; output is always green. Grayscale images have the same value in RGB')
    section_channel:EnumProperty(name='Source channel',items=CHANNELS,default='B',description='Channel to read from the section image; output is always blue')
    metal_value:IntProperty(name='Metallic',min=0,max=255,default=0,description='Constant red value when no metallic image is loaded: 0 nonmetal, 255 fully metallic')
    rough_value:IntProperty(name='Surface value',min=0,max=255,default=128,description='Constant roughness, or smoothness when My texture is a smoothness map is enabled; roughness is inverted into green')
    section_value:EnumProperty(name='Section',items=[('0','Lower (0)','Use the lower clothing region for the whole item'),('128','Middle (128)','Use the middle clothing region for the whole item'),('255','Upper (255)','Use the upper clothing region for the whole item')],default='128',description='Constant blue selector when no section image is loaded; leave Middle for one section over the whole item')
    width:IntProperty(name='Width',min=4,max=4096,default=1024,description='Output width in pixels; DDS export requires a power of two')
    height:IntProperty(name='Height',min=4,max=4096,default=1024,description='Output height in pixels; DDS export requires a power of two')
    input_smoothness:BoolProperty(name='Is Smoothness Map',default=False,description='Enable this if your texture is a SMOOTHNESS map instead of a roughness map. Enabled: copies it directly into green. Disabled: inverts roughness into green smoothness')
    snap_sections:BoolProperty(name='Snap to three sections',default=False,description='Map blue values to 0, 128 or 255. Disable for continuous blending or exact channel repacking')
    output_name:StringProperty(name='Image name',default='ReSkate Base Mask',description='Name for newly created mask images; generation may reuse the currently selected output')
    preview_channel:EnumProperty(name='View',items=[('RGB','Packed RGB','Show the complete generated base mask'),('R','Metalness','Show the red channel as grayscale'),('G','Smoothness','Show the green channel as grayscale'),('B','Sections','Show the blue selector as grayscale')],default='RGB',description='Choose the generated image or a grayscale channel preview; exports always use the generated mask')

class RSM_OT_Load(bpy.types.Operator,ImportHelper):
    bl_idname='rsm.load';bl_label='Load Data Texture'
    bl_description='Load an image for this input and mark it as Non-Color numerical data'
    filter_glob:StringProperty(default='*.png;*.dds;*.tga;*.jpg;*.jpeg;*.tif;*.exr',options={'HIDDEN'})
    target:StringProperty(description='Input slot that receives the loaded image',options={'HIDDEN'})
    def execute(self,context):
        try:
            im=bpy.data.images.load(self.filepath,check_existing=True);im.colorspace_settings.name='Non-Color';setattr(context.scene.rsm,self.target+'_image',im)
            self.report({'INFO'},'Loaded as Non-Color data');return {'FINISHED'}
        except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}

class RSM_OT_Generate(bpy.types.Operator):
    bl_idname='rsm.generate';bl_label='Generate Base Mask';bl_options={'REGISTER','UNDO'}
    bl_description='Pack the current inputs into red metalness, green smoothness, blue sections and opaque alpha; update after input changes'
    def execute(self,context):
        try:
            s=context.scene.rsm;a=build_pixels(s);im=s.output_image
            if im and im in [s.metal_image,s.rough_image,s.section_image]:raise ValueError('Output cannot also be an input.')
            if im is None or tuple(im.size)!=(s.width,s.height):
                im=bpy.data.images.new(s.output_name,width=s.width,height=s.height,alpha=True);s.output_image=im
            im.colorspace_settings.name='Non-Color';im.alpha_mode='CHANNEL_PACKED';im.pixels.foreach_set((a.astype(np.float32)/255).ravel());im.update();im.pack()
            self.report({'INFO'},'Generated mask; alpha is opaque');return {'FINISHED'}
        except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}

class RSM_OT_Preview(bpy.types.Operator):
    bl_idname='rsm.preview';bl_label='Show Preview'
    bl_description='Display the generated mask or selected channel in the Image Editor; does not change the exported mask'
    def execute(self,context):
        s=context.scene.rsm
        if not s.output_image:self.report({'ERROR'},'Generate a mask first');return {'CANCELLED'}
        im=s.output_image
        if s.preview_channel!='RGB':
            a=image_pixels(im);i={'R':0,'G':1,'B':2}[s.preview_channel];v=a[:,:,i];a[:,:,:3]=v[:,:,None]
            name='ReSkate Channel Preview';im=bpy.data.images.get(name) or bpy.data.images.new(name,width=a.shape[1],height=a.shape[0])
            if tuple(im.size)!=(a.shape[1],a.shape[0]):im.scale(a.shape[1],a.shape[0])
            im.colorspace_settings.name='Non-Color';im.pixels.foreach_set((a.astype(np.float32)/255).ravel());im.update()
        area=next((x for x in context.screen.areas if x.type=='IMAGE_EDITOR'),None)
        if area is None:area=context.area;area.type='IMAGE_EDITOR'
        area.spaces.active.image=im;return {'FINISHED'}

class RSM_OT_Export(bpy.types.Operator,ExportHelper):
    bl_idname='rsm.export';bl_label='Export Base Mask'
    bl_description='Save the last generated mask as lossless PNG or BC1 DDS with mipmaps; regenerate first if inputs changed'
    @classmethod
    def description(cls, context, properties):
        return 'Save the generated mask as BC1_UNORM DDS with a full mip chain; lossy, power-of-two dimensions required' if properties.format=='DDS' else 'Save the generated mask as lossless 8-bit RGBA PNG with exact channel values'
    filename_ext='.png'
    filter_glob:StringProperty(default='*.png;*.dds',options={'HIDDEN'})
    format:EnumProperty(name='Format',items=[('PNG','PNG (lossless)','Preserve exact 8-bit RGBA values'),('DDS','DDS BC1 + mipmaps','Lossy BC1_UNORM texture with a full mip chain')],default='PNG',description='Output file format')
    def execute(self,context):
        try:
            s=context.scene.rsm
            if not s.output_image:raise ValueError('Generate a mask first. Export saves the current generated image.')
            a=image_pixels(s.output_image);path=bpy.path.ensure_ext(str(Path(self.filepath).with_suffix('')),'.dds' if self.format=='DDS' else '.png')
            if self.format=='DDS':
                if any(n&(n-1) for n in s.output_image.size):raise ValueError('DDS export requires power-of-two dimensions.')
                dds_write(path,a)
            else:png_write(path,a)
            self.report({'INFO'},'Saved '+path);return {'FINISHED'}
        except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}


def split_layers(a, include_smoothness=False):
    layers={'Metallic':a[:,:,0],'Roughness':255-a[:,:,1],
            'SectionSelector':a[:,:,2],'Alpha':a[:,:,3]}
    if include_smoothness:layers['Smoothness']=a[:,:,1]
    return layers

class RSM_OT_Unpack(bpy.types.Operator):
    bl_idname='rsm.unpack';bl_label='Unpack Base Mask';bl_options={'REGISTER','UNDO'}
    bl_description='Extract metallic, roughness, one complete blue selector and alpha; optionally include smoothness and export PNGs'
    def execute(self,context):
        try:
            s=context.scene.rsm;source=s.unpack_image
            if source is None:raise ValueError('Select or load a base mask first.')
            if source.colorspace_settings.name!='Non-Color':raise ValueError('Set the source image color space to Non-Color first.')
            if not source.size[0] or not source.size[1]:raise ValueError('The source image has no pixel data.')
            layers=split_layers(image_pixels(source),s.unpack_smoothness)
            stem=bpy.path.clean_name(Path(source.name).stem) or 'BaseMask'
            folder=None
            if s.unpack_export:
                if not s.unpack_folder:raise ValueError('Choose an export folder.')
                folder=Path(bpy.path.abspath(s.unpack_folder))
                if not folder.is_dir():raise ValueError('Export folder must already exist.')
                conflicts=[str(folder/(stem+'_'+key+'.png')) for key in layers if (folder/(stem+'_'+key+'.png')).exists()]
                if conflicts:raise ValueError('Export files already exist; choose a different folder to avoid overwriting.')
            images={}
            for key,plane in layers.items():
                rgba=np.zeros((*plane.shape,4),np.uint8)
                if key=='SectionSelector':rgba[:,:,2]=plane
                else:rgba[:,:,:3]=plane[:,:,None]
                rgba[:,:,3]=255
                im=bpy.data.images.new(stem+'_'+key,width=plane.shape[1],height=plane.shape[0],alpha=True)
                im.colorspace_settings.name='Non-Color';im.alpha_mode='CHANNEL_PACKED'
                im.pixels.foreach_set((rgba.astype(np.float32)/255).ravel());im.update();im.pack();images[key]=im
                if folder:png_write(folder/(stem+'_'+key+'.png'),rgba)
            if s.unpack_repack:
                s.metal_image=images['Metallic'];s.rough_image=images['Roughness'];s.section_image=images['SectionSelector']
                s.metal_channel='R';s.rough_channel='G';s.section_channel='B'
                s.input_smoothness=False;s.snap_sections=False;s.width=source.size[0];s.height=source.size[1]
            self.report({'INFO'},f'Created {len(images)} layer images'+(' and exported PNGs' if folder else ''))
            return {'FINISHED'}
        except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}

PRESET_FIELDS=('metal_channel','rough_channel','section_channel','metal_value','rough_value',
    'section_value','width','height','input_smoothness','snap_sections','output_name','preview_channel',
    'unpack_smoothness','unpack_export','unpack_repack')

class RSM_OT_ResetDefaults(bpy.types.Operator):
    bl_idname='rsm.reset_defaults';bl_label='Reset Defaults';bl_options={'REGISTER','UNDO'}
    bl_description='Restore default settings and clear input image slots. Snapping and smoothness toggles are OFF. Keeps generated images and saved presets'
    def execute(self,context):
        s=context.scene.rsm
        for key in PRESET_FIELDS+('metal_image','rough_image','section_image','unpack_image','unpack_folder'):
            s.property_unset(key)
        RSM_MT_Presets.bl_label='Default'
        self.report({'INFO'},'Defaults restored; generated images preserved')
        return {'FINISHED'}

class RSM_MT_Presets(bpy.types.Menu):
    bl_label='Default';preset_subdir='reskate_mask_maker';preset_operator='script.execute_preset'
    def draw(self,context):
        self.layout.operator('rsm.default_preset',text='Default')
        self.layout.separator()
        bpy.types.Menu.draw_preset(self,context)

class RSM_OT_DefaultPreset(bpy.types.Operator):
    bl_idname='rsm.default_preset';bl_label='Default'
    bl_description='Apply built-in default settings without clearing input textures or generated images'
    def execute(self,context):
        for key in PRESET_FIELDS:context.scene.rsm.property_unset(key)
        RSM_MT_Presets.bl_label='Default'
        return {'FINISHED'}

class RSM_OT_DeletePreset(AddPresetBase,bpy.types.Operator):
    bl_idname='rsm.delete_preset';bl_label='Delete Preset'
    bl_description='Delete the currently selected saved preset. The built-in Default preset cannot be deleted'
    preset_menu='RSM_MT_Presets';preset_subdir='reskate_mask_maker'
    remove_active:BoolProperty(default=True,options={'HIDDEN'})
    @classmethod
    def poll(cls,context):return RSM_MT_Presets.bl_label not in {'Presets','Default'}
    def invoke(self,context,event):return context.window_manager.invoke_confirm(self,event)

class RSM_OT_RenamePreset(bpy.types.Operator):
    bl_idname='rsm.rename_preset';bl_label='Rename Preset'
    bl_description='Rename the selected saved preset without changing its settings; Default is protected'
    name:StringProperty(name='New name',description='New display name for the selected preset')
    @classmethod
    def poll(cls,context):return RSM_MT_Presets.bl_label not in {'Presets','Default'}
    def invoke(self,context,event):
        self.name=RSM_MT_Presets.bl_label
        return context.window_manager.invoke_props_dialog(self)
    def execute(self,context):
        try:
            label=RSM_MT_Presets.bl_label
            if label in {'Presets','Default'}:raise ValueError('Select a saved preset first.')
            new_name=self.name.strip()
            if not new_name or new_name.casefold()=='default':raise ValueError('Choose a non-empty name other than Default.')
            old=bpy.utils.preset_find(label,'reskate_mask_maker',display_name=True)
            if not old:raise ValueError('Selected preset file was not found.')
            old=Path(old).resolve()
            # Match Blender preset filename conventions and keep the file in its original directory.
            filename=bpy.path.clean_name(new_name).strip('. ')
            if not filename:raise ValueError('The name contains no usable characters.')
            dest=old.with_name(filename+old.suffix)
            if dest==old:
                RSM_MT_Presets.bl_label=bpy.path.display_name(str(old));return {'FINISHED'}
            if dest.exists():raise ValueError('A preset with that name already exists.')
            old.rename(dest)
            RSM_MT_Presets.bl_label=bpy.path.display_name(str(dest))
            self.report({'INFO'},'Preset renamed');return {'FINISHED'}
        except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}

class RSM_OT_SavePreset(AddPresetBase,bpy.types.Operator):
    bl_idname='rsm.save_preset';bl_label='Save Preset'
    bl_description='Save a named settings preset for reuse across Blender files. Stores settings, not input textures or generated images'
    preset_menu='RSM_MT_Presets';preset_subdir='reskate_mask_maker'
    preset_defines=['s = bpy.context.scene.rsm']
    preset_values=['s.'+key for key in PRESET_FIELDS]

class RSM_PT_Inputs(bpy.types.Panel):
    bl_label='Generate Base Mask';bl_idname='RSM_PT_layout2_generate';bl_space_type='IMAGE_EDITOR';bl_region_type='UI';bl_category='ReSkate';bl_order=0
    def draw_header(self,context):
        self.layout.label(text='',icon='TEXTURE')
    def draw(self,context):
        s=context.scene.rsm;l=self.layout
        l.use_property_split=True;l.use_property_decorate=False
        for key,title in [('metal','Metallic Map (R)'),('rough','Roughness Map (G)'),('section','Section Map (B)')]:
            if key!='metal':l.separator(factor=.6)
            l.label(text=title)
            row=l.row(align=True);row.prop(s,key+'_image',text='');op=row.operator('rsm.load',text='',icon='FILE_FOLDER');op.target=key
            if getattr(s,key+'_image'):
                l.prop(s,key+'_channel',text='Channel')
                if getattr(s,key+'_image').colorspace_settings.name!='Non-Color':l.label(text='Use Non-Color input',icon='ERROR')
            else:l.prop(s,key+'_value',text='Roughness' if key=='rough' else ('Value' if key!='section' else 'Section'))
            if key=='rough':
                l.prop(s,'input_smoothness')
                if s.input_smoothness:l.label(text='Copies input; skips inversion',icon='INFO')
        l.separator();l.operator('rsm.generate',icon='IMAGE_DATA')

class RSM_PT_Output(bpy.types.Panel):
    bl_label='Output';bl_idname='RSM_PT_layout2_output';bl_space_type='IMAGE_EDITOR';bl_region_type='UI';bl_category='ReSkate'
    bl_order=1
    bl_options={'DEFAULT_CLOSED'}
    def draw_header(self,context):
        self.layout.label(text='',icon='EXPORT')
    def draw(self,context):
        s=context.scene.rsm;l=self.layout;l.use_property_split=True;l.use_property_decorate=False
        l.prop(s,'output_image',text='Mask');l.prop(s,'preview_channel');l.operator('rsm.preview',icon='HIDE_OFF')
        row=l.row(align=True);row.enabled=s.output_image is not None
        op=row.operator('rsm.export',text='PNG',icon='IMAGE_DATA');op.format='PNG';op=row.operator('rsm.export',text='DDS',icon='EXPORT');op.format='DDS'

class RSM_PT_Settings(bpy.types.Panel):
    bl_label='Settings';bl_idname='RSM_PT_layout2_settings';bl_space_type='IMAGE_EDITOR';bl_region_type='UI';bl_category='ReSkate';bl_options={'DEFAULT_CLOSED'}
    bl_order=4
    def draw_header(self,context):
        self.layout.label(text='',icon='PREFERENCES')
    def draw(self,context):
        s=context.scene.rsm;l=self.layout;l.use_property_split=True;l.use_property_decorate=False
        l.prop(s,'width');l.prop(s,'height');l.prop(s,'output_name');l.prop(s,'snap_sections');l.operator('rsm.reset_defaults',icon='FILE_REFRESH')

class RSM_PT_Presets(bpy.types.Panel):
    bl_label='Presets';bl_idname='RSM_PT_layout2_presets';bl_space_type='IMAGE_EDITOR';bl_region_type='UI';bl_category='ReSkate';bl_options={'DEFAULT_CLOSED'}
    bl_order=3
    def draw_header(self,context):
        self.layout.label(text='',icon='PRESET')
    def draw(self,context):
        l=self.layout
        l.menu('RSM_MT_Presets',text=RSM_MT_Presets.bl_label,icon='PRESET')
        row=l.row(align=True);row.operator('rsm.save_preset',text='Save',icon='FILE_TICK');row.operator('rsm.rename_preset',text='Rename',icon='GREASEPENCIL');row.operator('rsm.delete_preset',text='Delete',icon='TRASH')

class RSM_PT_Unpack(bpy.types.Panel):
    bl_label='Unpack Base Mask';bl_idname='RSM_PT_layout2_unpack';bl_space_type='IMAGE_EDITOR';bl_region_type='UI';bl_category='ReSkate';bl_options={'DEFAULT_CLOSED'}
    bl_order=2
    def draw_header(self,context):
        self.layout.label(text='',icon='IMPORT')
    def draw(self,context):
        s=context.scene.rsm;l=self.layout;l.use_property_split=True;l.use_property_decorate=False
        row=l.row(align=True);row.prop(s,'unpack_image',text='');op=row.operator('rsm.load',text='',icon='FILE_FOLDER');op.target='unpack'
        l.prop(s,'unpack_repack');l.prop(s,'unpack_smoothness');l.prop(s,'unpack_export')
        if s.unpack_export:l.prop(s,'unpack_folder')
        l.operator('rsm.unpack',icon='IMAGE_DATA')

classes=(RSM_Settings,RSM_OT_Load,RSM_OT_Generate,RSM_OT_Preview,RSM_OT_Export,RSM_OT_Unpack,RSM_OT_ResetDefaults,RSM_MT_Presets,RSM_OT_DefaultPreset,RSM_OT_SavePreset,RSM_OT_RenamePreset,RSM_OT_DeletePreset,RSM_PT_Inputs,RSM_PT_Output,RSM_PT_Unpack,RSM_PT_Presets,RSM_PT_Settings)

def register():
    for c in classes:bpy.utils.register_class(c)
    bpy.types.Scene.rsm=PointerProperty(type=RSM_Settings)
    RSM_MT_Presets.bl_label='Default'
def unregister():
    del bpy.types.Scene.rsm
    for c in reversed(classes):bpy.utils.unregister_class(c)
