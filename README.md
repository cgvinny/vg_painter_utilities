# VG Painter Utilities (vg_pt_utils)

**VG Painter Utilities (vg_pt_utils)** is a suite of tools and shortcuts designed to add functionalities to Substance 3D Painter.

Feel free to use, reuse and adapt this content to your needs
(Please read the [LICENSE](LICENSE) file for more information)

Contact me for any issue of feedback: cgvinny@adobe.com

## Installation
Installation and details in this [https://youtu.be/KjRgUkQnXDk ](video) here

1. Copy:the 'plugins' & 'modules' folders into the 'python' folder located here by default (please adapt: if your location is different) 

   `C:\Users\[USER]\Documents\Adobe\Adobe Substance 3D Painter\python`

3. You will have a warning that this folder already exists: you can proceed safely, as it will just add content, or replace the previous version of the script.


    

## Usage

***VG Menu Launcher***

Once activated, a new "VG Utilities" will be added to the top bar, giving access to the different tools, and shortcuts will be activated. 

### Activation 
In Substance 3D Painter; go to the "Python" top menu and reload the plugins folder: "vg_menu_launcher" should be present


### Features
New Paint layer ( `Ctrl + P` )

---
New Fill layer with Base Color activated ( `Ctrl + F` )

New Fill layer with Height activated ( `Ctrl + Alt + F` )

New Fill layer, all channels activated ( `Ctrl + Shift + F` )

New Fill layer, no  channels activated ( `Alt + F` )

---
Add mask to selected layer. If a mask is already present, it will switch it from black to white, or from white to black ( `Ctrl + M` )

Add mask with a fill effect to selected layer. If a mask is already present, it will switch it from black to white, or from white to black ( `Shift + M` )

Add black mask with AO Generator ( `Ctrl + Shift + M` )

Add black mask Curvature Generator ( `Ctrl + alt + M` )

---
Create new layer from what is visible in the stack (so you can delete these layers if you don't need to edit them anymore, thus improving performances.).Note that normal channel is deactivated, to avoid generatin normal information twice with the height map ( `Ctrl + shift + G` )


Create Reference point layer ( `Ctrl + R` )

---
Bake current Texture Set mesh maps ( `Ctrl + B` )
