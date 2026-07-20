# سَنَد — self-hosted subset fonts

Two woff2 files replace the 16 Google-Fonts requests. Subset to the Arabic
block plus Basic/Latin-1 and the punctuation the interface uses.

| file | family in CSS | source | weight | license |
|---|---|---|---|---|
| `sanad-text.woff2` | IBM Plex Sans Arabic (also backs the UI/Noto-Kufi slots) | IBM Plex Sans Arabic Regular | 400 | OFL-1.1 |
| `sanad-display.woff2` | Amiri (display/headline slot) | Markazi Text @ wght 700 | 700 | OFL-1.1 |

Rebuild: `pyftsubset <src>.ttf --flavor=woff2 --layout-features='ccmp,isol,init,medi,fina,rlig,calt,liga,mark,mkmk,kern' --unicodes='U+0020-00FF,U+0600-06FF,U+0750-077F,U+200C-200F,U+2010-2015,U+2018-201F,U+2039-203A'`
