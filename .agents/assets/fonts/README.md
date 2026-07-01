Licensed local fonts for isolated agent jobs.

Put licensed font files here on the deployment host, for example:

- `msyh.ttc`
- `msyh.ttf`
- `msyhbd.ttc`
- `MicrosoftYaHei.ttf`
- `NotoSansSC-Regular.otf`
- `NotoSansSC-Bold.otf`

Font binaries are intentionally ignored by git. The Daily Writer artwork job copies
this directory into each isolated workdir and asks render scripts to use these files
before any system font fallback.
