# VG Painter Utilities (vg_pt_utils)

**VG Painter Utilities (vg_pt_utils)** is a suite of tools and shortcuts designed to add functionality to Substance 3D Painter.

Feel free to use, reuse and adapt this content to your needs
(Please read the [LICENSE](LICENSE) file for more information)

Contact me for any issue of feedback: cgvinny@adobe.com

## Installation
Installation and details in this [https://youtu.be/KjRgUkQnXDk ](video) here

1. Copy:the 'plugins' & 'modules' folders into the 'python' folder located here by default (please adapt: if your location is different) 

   `C:\Users\[USER]\Documents\Adobe\Adobe Substance 3D Painter\python`

3. You will have a warning that this folder already exists: you can proceed safely, as it will just add content, or replace the previous version of the script.


    

## Usage

***VG Shortcuts Launcher***

Once activated, The `VG shortcuts launcher` plugin will add a collection of shorcuts to Substance 3D Painter

### Activation 
In Substance 3D Painter; go to the "Python" top menu and reload the plugins folder: "vg_shortcuts_launcher" should be present


### Shortcuts
`Ctrl + P`: new Paint layer

---
`Ctrl + F`: new Fill layer with Base Color activated

`Ctrl + Alt + F`: new Fill layer with Height activated

`Ctrl + Shift + F`: new Fill layer, all channels activated

---
`Ctrl + M`: add mask to selected layer. If a mask is already present, it will switch it from black to white, or from white to black

`Ctrl + Shift + M`: add black mask with AO Generator

`Ctrl + alt + M`: add black mask Curvature Generator

---
`Ctrl + shift + G`: Create new layer from what is visible in the stack (so you can delete these layers if you don't need to edit them anymore, thus improving performances.). Only works with the basic PBR channels at the moment (Base Color, Metal, roughness, height, Normal). Note that normal channel is deactivated, to avoid generatin normal information twice with the height map.