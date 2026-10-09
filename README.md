# ReSkate-Base-Mask-Packer

A Blender 5.2 extension for creating and unpacking Skate / ReSkate clothing base-mask textures without baking.

Pack metallic, roughness, and section maps into one texture, or extract editable maps from an existing base mask. Includes channel previews, PNG and DDS export, and reusable settings presets.

## Requirements

- Blender 5.2 or later. Tested with Blender 5.2.0 LTS; later versions have not been independently tested.
- No additional Python packages or external texture converters are required.
- Input textures must share the model's UV layout.

## Installation

1. Download `ReSkate-Base-Mask-Packer-1.14.3.zip` from the repository's [Releases](https://github.com/donajello/ReSkate-Base-Mask-Packer/releases), once a release is published.
2. In Blender, open **Edit > Preferences > Get Extensions**.
3. Open the menu at the top right and select **Install from Disk**.
4. Select the extension ZIP without extracting it, and enable the extension.
5. Open an **Image Editor**, press **N**, and select the **ReSkate** sidebar tab.

Use the installable extension ZIP, not the GitHub source archive. When updating, save your work first. If Blender does not replace an existing installation, uninstall the old extension and install the new ZIP. Restart Blender if old code remains loaded.

The extension retains its original internal ID, `reskate_mask_maker`, for compatibility with earlier versions named ReSkate Mask Maker.

## How the mask is packed

| Base-mask channel | Meaning | Input |
| --- | --- | --- |
| **Red** | Metalness | Metallic map or constant |
| **Green** | Smoothness | Automatically inverted roughness, or an existing smoothness map |
| **Blue** | Clothing material-section selector | Section map or constant |
| **Alpha** | Opaque | Always 255 when generating |

This layout was identified in the clothing shader embedded in the inspected ReSkate Studio installation. Other material paths, including boards, can handle blue differently. Equivalent behavior in Skate's game shaders has not been independently verified.

## Generate Base Mask

### Metallic Map (R)

Choose an existing image or load one with the folder button. The source channel defaults to **Red**. With no image, use a constant: **0** for nonmetal or **255** for fully metallic.

### Roughness Map (G)

Load your roughness map. The source channel defaults to **Green**; this works for grayscale maps because their RGB channels are equal.

Leave **Is Smoothness Map** **off** for roughness. The plugin calculates:

```text
green = 255 - roughness
```

Enable **Is Smoothness Map** only when your input is already smoothness or glossiness. This copies the input directly into green, skipping inversion. The same setting applies to constant values.

The generated base mask stores **smoothness in green**, even though the primary input is roughness.

### Section Map (B)

The source channel defaults to **Blue**. Leave the image empty and keep **Middle (128)** to use one material section over the whole item.

For clothing materials using discrete selection:

| Blue value | Region |
| --- | --- |
| 0-63 | Lower |
| 64-191 | Middle |
| 192-255 | Upper |

Region labels do not establish the numbering shown in Studio. Some materials blend regions continuously instead.

**Snap to three sections** is **off by default**. Enabling it maps blue values to 0, 128, or 255, which changes intermediate values. Leave it off when reconstructing an original mask.

### Generate

Set dimensions under **Settings**, then click **Generate Base Mask**. Inputs are resized to the chosen dimensions; section maps use nearest-neighbor sampling and surface maps use bilinear sampling.

The generated image uses **Non-Color** data and is packed into the Blender file. Regenerate after changing inputs. Albedo and normal textures stay separate.

Folder buttons mark loaded images as Non-Color. For images selected from existing Blender data, set their color space to Non-Color if the panel warns you.

## Output

Expand **Output** to preview Packed RGB, Metalness, Smoothness, or Sections.

- **PNG:** lossless 8-bit RGBA export of the generated values.
- **DDS:** BC1_UNORM with a DX10 header and a full mip chain. Requires power-of-two dimensions.

Exports use the generated base mask, not the separate channel preview. BC1 compression is lossy; re-exporting DDS can introduce differences. Mipmaps also blend boundaries. Use suitable UV padding and inspect detailed textures in ReSkate. The included BC1 encoder is a basic encoder.

## Unpack Base Mask

Load an existing Non-Color PNG or DDS and click **Unpack Base Mask**. By default it creates:

| Extracted image | Contents |
| --- | --- |
| Metallic | Original red values, shown as grayscale |
| Roughness | Inverted original green values, shown as grayscale |
| SectionSelector | Original blue values in blue only; red and green are zero |
| Alpha | Original alpha values, shown as grayscale |

The complete section selector always stays in **one image**. There is no section-splitting option.

**Export Smoothness Map** is **off by default**. Enable it to also create the original green channel as a standalone grayscale Smoothness image.

Enable **Export PNG layers** and select an existing folder to save the extracted images. Existing output filenames are protected; use another folder if they already exist.

Enable **Use layers as inputs** to populate the generation controls automatically. It supplies the extracted roughness map, disables smoothness input and section snapping, and matches the source dimensions. The blue-only selector must be read using **Blue**, which is set automatically.

### Reconstructing an original mask

1. Unpack with **Use layers as inputs** enabled.
2. Leave **Is Smoothness Map** and **Snap to three sections** off.
3. Keep the original dimensions.
4. Generate and export PNG.

The tested game DDS reproduced Blender's decoded RGBA values exactly using this path. DDS decoders may differ slightly in rounding, and recompressing to DDS can introduce new errors. Non-opaque source alpha is extracted separately; generated masks always use opaque alpha.

Unpacking retrieves stored channel data, not original authoring layers. It cannot recover information lost through compression, albedo, normal details, or procedural settings. Float inputs are clamped to 0-1 and quantized to 8-bit.

## Presets and defaults

Expand **Presets** to save, apply, rename, or delete named presets.

- **Default:** applies default settings while retaining loaded textures.
- **Save:** stores reusable settings, not textures or generated images.
- **Rename / Delete:** operate on the selected saved preset. Default is protected.
- **Settings > Reset Defaults:** restores settings and clears input selections while preserving generated images and saved presets.

Presets persist across Blender files on the same computer. Existing scenes retain their stored settings when the extension is updated; use Reset Defaults to restore current defaults.

## Interface

Panels appear in this order:

1. **Generate Base Mask** - open by default.
2. **Output** - collapsed by default.
3. **Unpack Base Mask** - collapsed by default.
4. **Presets** - collapsed by default.
5. **Settings** - collapsed by default.

Hover over controls for explanations. Images are loaded using dropdowns or folder buttons; custom drag-and-drop support is not included.

## Troubleshooting

- **Rebuilt mask looks different:** disable section snapping, use roughness with Is Smoothness Map off, and preserve source dimensions.
- **Section selector becomes black:** ensure its source channel is Blue, not Red, when using a blue-only selector image.
- **Export reflects older settings:** click Generate again before exporting.
- **Old panel ordering or labels remain:** restart Blender after updating.
- **DDS export rejects dimensions:** use power-of-two widths and heights, such as 512, 1024, or 2048.

## Build from source

Run the included packaging script with Python:

```sh
python build_release.py
```

It creates an installable extension ZIP under `dist/`. Blender supplies the runtime dependencies; the build script uses only Python's standard library.

To validate the ZIP with Blender:

```sh
blender --command extension validate dist/ReSkate-Base-Mask-Packer-1.14.3.zip
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

This is a community tool and is not affiliated with EA, Frostbite, or the ReSkate developers.
