# Fonts

The approved fonts for initial charms and engraved text (rules CH-06 and CH-07). All three
are licensed under the SIL Open Font License 1.1; the license of each is next to it.

| File | Font id | Source (downloaded 2026-11-17) | License |
|---|---|---|---|
| `Pacifico-Regular.ttf` | `pacifico` | [google/fonts](https://github.com/google/fonts) `ofl/pacifico/` | `OFL-Pacifico.txt` |
| `Cinzel-Bold.ttf` | `cinzel_bold` | [NDISCOVER/Cinzel](https://github.com/NDISCOVER/Cinzel) `fonts/ttf/` (static build) | `OFL-Cinzel.txt` |
| `Montserrat-ExtraBold.ttf` | `montserrat_extrabold` | [JulietaUla/Montserrat](https://github.com/JulietaUla/Montserrat) `fonts/ttf/` (static build) | `OFL-Montserrat.txt` |

The files are unmodified. Static builds are used instead of the variable fonts because
instancing a variable font keeps overlapping contours, which CadQuery turns into overlapping
solids (decision 0010). The minimum letter heights in CH-07 were measured on these files with
`python -m app.cli measure-fonts`.
