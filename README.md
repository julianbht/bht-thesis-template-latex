# BHT Thesis Template

LaTeX template for theses at Berliner Hochschule für Technik (BHT), supervised by Prof. Dr. Siamak Haschemi. Includes a custom BHT cover page with university branding and support for German and English.

## Directory Structure

- `main.tex` - Main document file
- `preamble.tex` - Package imports and configurations
- `macros.tex` - Custom LaTeX commands
- `bht-cover-page.sty` - BHT cover page style
- `layout.sty` - Layout configurations
- `chapters/` - Thesis chapters
- `bib/` - Bibliography files
- `figures/` - Images and diagrams
- `cover/` - University logo and cover assets
- `software/` - Helper scripts

## Getting Started

1. Clone this repository
2. Update the metadata in `main.tex`:
   - `\thesisTitle{}`
   - `\thesisSubtitle{}`
   - `\authorName{}`
   - `\studentId{}`
   - `\degreeProgram{}`
   - `\supervisorField{}`
3. Choose your language: `\selectlanguage{ngerman}` or `\selectlanguage{english}`
4. Edit chapters in the `chapters/` directory
