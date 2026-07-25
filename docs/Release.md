# Windows release packaging

## Build

From `barcode_generator/` (requires `pip install -e ".[build]"`):

```powershell
python release_build/build_windows_release.py
```

Or:

```powershell
release_build\build_release.bat
```

## Output

| Artifact | Location |
|----------|----------|
| Staged folder | `barcode_generator/dist/Classroom-Library-Label-Maker-<version>-windows/` |
| ZIP for GitHub Releases | `releases/Classroom-Library-Label-Maker-<version>-windows.zip` |

## Release folder layout

```
Classroom-Library-Label-Maker-<version>-windows/
├── Classroom Library Label Maker.exe   # windowed GUI (no console)
├── Sample Books.xlsx                   # teacher sample inventory
├── Quick Start.md                      # one-page teacher guide
├── README.md
├── LICENSE
└── VERSION.txt
```

Runtime assets (icons, sample workbook) are also embedded inside the EXE.
Diagnostic logs are written to:

`%LOCALAPPDATA%\Classroom Library Label Maker\logs\application.log`

## Notes

- The legacy `build.bat` / `barcode-generator.spec` build remains a **console CLI**
  developer artifact.
- Teachers should use the GUI ZIP above.
