## Mods
You can make your own mods
### Making mods
There are 3 ways of making a mod: providing a replacement file or for xml files a small diff with just the changes

First you have to determine which file to edit, say you want to change a value of a unit in the gamesettings file.

As you're reading this file you are in the mods directory. There are 2 mod directories, in the install folder and in the my games folder of this game. Currently the active-limited-edition mod is present as as mod. This allows being able to use these units while they were only obtainable in a specific time period a decade ago.

For this you see:


```
├── mods
│   └── active-limited-edition
│   │   └── assets
│   │       └── 29oct2012
│   │           └── gameSettings.xml.xmldiff
```

This will apply the differences to the `gameSettings.xml` file, another mod could add a different thing which is why it important to use diffs so multiple mods can work together.

### XMLDIFF
You need to create an `.xmldiff` file for the xml you want to replace


### JSON
The flash client reads the xml, the server reads a json that is converted from a xml. For a lot of things this file needs to be edition too.

For this there is a `.jsonpatch` possibility. 

See http://jsonpatch.com/

At https://json-patch-builder-online.github.io/ you can easily generate a patch online which would produce

```
[
    {
        "op": "replace",
        "path": "/settings/items/item/3577/unit/-strength",
        "value": "3000"
    }
]
```
This would change the strength of a Cadet Soldiers. note that it tries to locate the 3577th item, if any mod that precedes your mod tries to insert a unit between those numbers, this will try to change a diffenent item.

Save as `gameSettings.json.jsonpatch` directly in the mod's folder.

### Overwriting files
Other files could be replaced immediately e.g. by creating a `mods/mod_name/assets/sol_assets_octdict/assets/game/buildings/Buildings_Icons.swf`

## Running mods
If you have mods you can add them to the mods folder in your `My Games\RaiseTheEmpires\mods` folder. Mods should be unzipped so it's like the folder structure above.
