#   
# **ReSkate Base Mask Packer**  
A Blender extension that makes creating and editing **Skate / ReSkate clothing textures** easier. No baking or complicated setup required!  
You can:  
* **Create base masks** using metallic, roughness, and material section maps.  
* **Unpack existing base masks** into separate, editable images.  
* **Preview** individual texture channels.  
* **Export** your finished textures as PNG or DDS.  
* **Save presets** to reuse your settings.  
## **Installation**  
**Requires Blender 5.2 or newer.**  
1. Download the extension ZIP from ++[Releases](https://github.com/donajello/ReSkate-Base-Mask-Packer/releases)++.  
2. Open Blender and go to **Edit > Preferences > Get Extensions**.  
3. Click the menu in the top-right corner and choose **Install from Disk**.  
4. Select the ZIP file and enable the extension.  
5. Open the **Image Editor**, press **N**, and click the **ReSkate** tab.  
That’s it! You’re ready to go.  
## **What is a Base Mask?**  
A base mask is a texture that tells ReSkate how different parts of a clothing item should look and behave.  
It stores three types of information in one image:  

| Channel | What it controls                                            |
| ------- | ----------------------------------------------------------- |
| Red     | Metalness — how metallic a surface is                       |
| Green   | Smoothness — how shiny or rough a surface appears           |
| Blue    | Material sections — which areas can use different materials |
  
The extension handles combining these channels for you.  
## **Creating a Base Mask**  
1. Open **Generate Base Mask**.  
2. Select your **Metallic**, **Roughness**, and **Section** textures.  
3. Choose your output resolution under **Settings**.  
4. Click **Generate Base Mask**.  
5. Open **Output** to preview and export your texture.  
**Don’t have all three textures?** No problem! You can leave inputs empty and use the built-in default values.  
**Tip:** Leave **Is Smoothness Map** and **Snap to three sections** turned off unless you specifically need them.  
## **Editing an Existing Base Mask**  
Already have a base mask from Skate or ReSkate? You can unpack it into editable textures!  
1. Open **Unpack Base Mask**.  
2. Load your existing PNG or DDS texture.  
3. Enable **Use layers as inputs**.  
4. Click **Unpack Base Mask**.  
5. Edit the extracted textures in your preferred image editor.  
6. Load your edited textures, then click **Generate Base Mask** to rebuild.  
**Example: Converse Shoe**  
**Original base mask**  
**Extracted textures**  

| Metallic | Roughness | Material Sections |
| -------- | --------- | ----------------- |
|          |           |                   |
  
**Rebuilt base mask**  
The extension separates the original texture into editable maps, then combines them again when you’re finished.  
## **Exporting**  
Choose your preferred format under **Output**:  
* **PNG** — lossless image, ideal for editing and testing.  
* **DDS** — compressed game-texture format with mipmaps.  
For DDS export, use a resolution such as **512×512**, **1024×1024**, or **2048×2048**.  
Remember to click **Generate Base Mask** again after making changes!  
## **Presets**  
Save your favorite settings under **Presets** and reuse them across Blender projects. Presets save your settings, not the textures themselves.  
## **Troubleshooting**  
**My rebuilt mask looks different.** Turn off **Snap to three sections** and **Is Smoothness Map**, and use the original image resolution.  
**My material section map is black.** Make sure the source channel is set to **Blue**.  
**My exported texture hasn’t changed.** Click **Generate Base Mask** again before exporting.  
**My DDS won’t export.** Use power-of-two dimensions, such as 1024×1024.  
## **License**  
GPL-3.0-or-later. See ++[LICENSE](applewebdata://6658F5E5-51A9-4DD3-858C-A37B5193E263/LICENSE)++.  
This is an unofficial community tool and is not affiliated with EA, Frostbite, or the ReSkate developers.  
Original game textures shown in the examples belong to their respective owners.  
