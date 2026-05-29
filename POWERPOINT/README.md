# 📊 PowerPoint Brain Reference Folder

This folder serves as the local workspace for the `PowerPointBrain`.

## Usage
1. Place slide notes in a text file named `slides_notes.txt`.
2. Format the file using markdown or a simple structure, for example:
   ```markdown
   # Presentation Title
   Subtitle here
   
   ## Slide 1 Title
   - Point 1
   - Point 2
   
   ## Slide 2 Title
   - Point A
   - Point B
   ```
3. Trigger the `POWERPOINT` brain. It will read `slides_notes.txt`, compile the slides, and generate:
   - `presentation.pptx` (PowerPoint format, using `python-pptx` if installed)
   - `presentation_preview.html` (HTML deck fallback)
