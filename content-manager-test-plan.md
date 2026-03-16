# Content Manager Phase 1 — Test Plan

> Paste this into Claude Code and ask it to run through every test.
> Prerequisite: .venv activated, ANTHROPIC_API_KEY set, app running.

---

## Instructions for Claude

Run through every test below in order. For each test:
1. Execute the test steps exactly as described
2. Record PASS or FAIL
3. If FAIL, describe what went wrong
4. At the end, produce a summary table of all test results
5. Fix any FAILs you find

Start the Streamlit app before beginning UI tests:
```
streamlit run app.py --server.headless true &
```

---

## SECTION 1: Data Layer

### DL1 — Content Pieces Catalog

DL1.1 Catalog file exists
- Run: python -c "import json; json.load(open('catalogs/content_pieces.json')); print('OK')"
- EXPECTED: Prints "OK", valid JSON, array structure

DL1.2 CRUD module exists
- Check modules/config/content_catalog.py
- EXPECTED: File exists with get_content_pieces(), get_content_piece(id), save_content_piece(), delete_content_piece()

DL1.3 Filter functions
- EXPECTED: Can filter by type, status, and tags

DL1.4 ID generation
- EXPECTED: New content pieces get IDs with cp_ prefix + 8 hex chars

DL1.5 Schema completeness
- EXPECTED: save_content_piece() accepts and stores: id, title, type, status, created_at, updated_at, tags, charts, commentary, export_history

### DL2 — House View Catalog

DL2.1 House View file exists
- Run: python -c "import json; d=json.load(open('catalogs/house_view.json')); print(f'Title: {d[\"title\"]}, Sections: {len(d[\"sections\"])}')"
- EXPECTED: Prints title and non-zero section count

DL2.2 Pre-populated sections
- EXPECTED: Sections exist for major themes from config/tags.json (rates, credit, labor, housing, manufacturing, inflation, monetary-policy at minimum)

DL2.3 Section structure
- EXPECTED: Each section has theme, title (human-readable), and bullets (empty array)

DL2.4 CRUD module exists
- Check modules/config/house_view_catalog.py
- EXPECTED: load_house_view(), save_house_view(), add_section(), delete_section(), add_bullet(), update_bullet(), delete_bullet(), attach_chart_to_bullet()

DL2.5 Auto-backup
- EXPECTED: save_house_view() creates catalogs/house_view_backup.json before writing

DL2.6 Timestamp update
- EXPECTED: save_house_view() updates last_updated field automatically

---

## SECTION 2: Chart Picker Component

### CP1 — Component Exists

CP1.1 File exists
- Check components/content_chart_picker.py
- EXPECTED: File exists with a callable function/component

### CP2 — Research Charts Tab

CP2.1 Shows News Reader charts
- EXPECTED: Displays charts from catalogs/news.json chart_images

CP2.2 Filters available
- EXPECTED: Source filter, tag filter, date range filter

CP2.3 Content-flagged charts prioritized
- EXPECTED: Charts with flagged_for_content=true appear first or are highlighted

CP2.4 Chart display
- EXPECTED: Each chart shows thumbnail, caption, source badge, date

### CP3 — Dashboard Charts Tab

CP3.1 Shows Dashboard charts
- EXPECTED: Displays charts from catalogs/charts.json

CP3.2 Tag filter
- EXPECTED: Can filter dashboard charts by tags

CP3.3 Thumbnail rendering
- EXPECTED: Shows rendered preview of Plotly charts (via kaleido or placeholder with title)

### CP4 — Selection Behavior

CP4.1 Click to select
- EXPECTED: Clicking a chart toggles selection (visual indicator like blue border)

CP4.2 Selected strip
- EXPECTED: Selected charts appear in a strip/summary area showing order

CP4.3 Reorder
- EXPECTED: Selected charts can be reordered (up/down buttons or numbered positions)

CP4.4 Pre-selection support
- EXPECTED: Component accepts pre-selected chart list for editing existing pieces

---

## SECTION 3: Content Composer View

### CC1 — Page and Navigation

CC1.1 Page loads
- EXPECTED: views/content_composer.py exists and is routed in app.py

CC1.2 Sidebar navigation
- EXPECTED: "Content Composer" appears in sidebar under Content section

CC1.3 Empty state
- EXPECTED: Shows empty draft list with "New Email Update" button when no drafts exist

### CC2 — Draft Management

CC2.1 Create new draft
- EXPECTED: "New Email Update" button creates a new content piece with type=email_update and status=draft

CC2.2 Draft list
- EXPECTED: Existing drafts shown with title, type badge, date, chart count, status

CC2.3 Load draft
- EXPECTED: Clicking a draft loads it into the editor

CC2.4 Delete draft
- EXPECTED: Can delete a draft (with confirmation)

### CC3 — Chart Selection

CC3.1 Add Charts button
- EXPECTED: Opens the chart picker component

CC3.2 Charts display in grid
- EXPECTED: Selected charts shown in 2-column layout with image and caption

CC3.3 Caption editing
- EXPECTED: Caption below each chart is editable (text input)

CC3.4 Remove chart
- EXPECTED: X button removes chart from the piece

CC3.5 Reorder charts
- EXPECTED: Up/down buttons change chart position

### CC4 — Commentary

CC4.1 Generate Draft button
- EXPECTED: Button exists, sends charts to Claude API

CC4.2 AI generation works
- EXPECTED: Clicking Generate Draft returns 3-5 bullet points (may take a few seconds with spinner)
- NOTE: Requires ANTHROPIC_API_KEY to be set

CC4.3 AI badge
- EXPECTED: AI-generated bullets have an "AI" badge/indicator

CC4.4 Edit bullets
- EXPECTED: Each bullet is an editable text area

CC4.5 AI badge clears on edit
- EXPECTED: Editing an AI-generated bullet removes the AI badge

CC4.6 Add bullet
- EXPECTED: Can add a new blank bullet

CC4.7 Delete bullet
- EXPECTED: Can remove a bullet with X button

CC4.8 Reorder bullets
- EXPECTED: Up/down arrows change bullet order

### CC5 — Save and Export

CC5.1 Save Draft
- EXPECTED: Saves to catalogs/content_pieces.json
- Verify: python -c "import json; d=json.load(open('catalogs/content_pieces.json')); print(f'{len(d)} pieces')"

CC5.2 Title saves
- EXPECTED: Title field value persists after save

CC5.3 Tags save
- EXPECTED: Selected tags persist after save

CC5.4 Preview
- EXPECTED: Shows composed content in email HTML layout (charts in grid, bullets above, header/footer)

CC5.5 Copy HTML
- EXPECTED: Renders email HTML and provides it for copying (via st.code or copy button)

CC5.6 Status indicator
- EXPECTED: Shows "Draft saved at HH:MM" or similar after save

---

## SECTION 4: House View

### HV1 — Page and Navigation

HV1.1 Page loads
- EXPECTED: views/house_view.py exists and is routed in app.py

HV1.2 Sidebar navigation
- EXPECTED: "House View" appears in sidebar under Content section

HV1.3 Header displays
- EXPECTED: Shows "Kennedy Lewis — House View" title and last updated timestamp

### HV2 — Sections

HV2.1 Theme sections displayed
- EXPECTED: All sections from catalogs/house_view.json rendered with theme headers

HV2.2 Empty section message
- EXPECTED: Sections with no bullets show "(no bullets yet)" or similar

HV2.3 Add section
- EXPECTED: Can add a new section with theme dropdown and title

HV2.4 Delete section
- EXPECTED: Can delete a section (with confirmation)

### HV3 — Bullets

HV3.1 Add bullet
- EXPECTED: [+ Add Bullet] button adds a blank bullet to the section

HV3.2 Edit bullet inline
- EXPECTED: Click to edit toggles bullet text to a text input. Saving updates the text.

HV3.3 Timestamp auto-updates
- EXPECTED: Editing a bullet updates its updated_at timestamp

HV3.4 Delete bullet
- EXPECTED: [x] button removes the bullet (with confirmation)

HV3.5 Attach chart
- EXPECTED: [📊] button opens a mini chart picker to attach supporting charts

HV3.6 Chart thumbnails displayed
- EXPECTED: Bullets with supporting charts show small thumbnails

HV3.7 Detach chart
- EXPECTED: Can remove an attached chart from a bullet

### HV4 — Persistence

HV4.1 Auto-save
- EXPECTED: Changes save automatically to catalogs/house_view.json

HV4.2 Backup created
- EXPECTED: catalogs/house_view_backup.json exists after first save

HV4.3 Survives page reload
- EXPECTED: After adding bullets and reloading the page, bullets are still there

HV4.4 Last updated timestamp
- EXPECTED: Header shows correct last_updated time after edits

### HV5 — Export Placeholders

HV5.1 Export PDF button
- EXPECTED: Button exists (can be placeholder that shows "Coming in Phase 2" message)

HV5.2 Export Word button
- EXPECTED: Button exists (can be placeholder)

---

## SECTION 5: Integration

### INT1 — Chart References

INT1.1 News Reader charts in composer
- EXPECTED: Charts from catalogs/news.json selectable in the chart picker

INT1.2 Dashboard charts in composer
- EXPECTED: Charts from catalogs/charts.json selectable in the chart picker

INT1.3 Chart images resolve
- EXPECTED: Selected charts display their images correctly (no broken images)

INT1.4 News Reader flagged charts
- EXPECTED: Charts flagged for content use in News Reader appear in the chart picker (prioritized or highlighted)

### INT2 — Shared Tags

INT2.1 Content pieces use shared vocabulary
- EXPECTED: Tag picker in Content Composer uses tags from config/tags.json

INT2.2 House View sections match themes
- EXPECTED: House View section themes correspond to tags in config/tags.json

### INT3 — AI Integration

INT3.1 Anthropic SDK available
- Run: python -c "import anthropic; print('OK')"
- EXPECTED: Prints OK

INT3.2 Commentary generation prompt
- Check the AI generation code in content_composer.py
- EXPECTED: Sends chart images and captions to Claude with a prompt about macro analysis at KL

INT3.3 Error handling
- EXPECTED: If API call fails, shows error message and lets user write bullets manually

### INT4 — Navigation

INT4.1 All Content section pages accessible
- EXPECTED: Sidebar Content section includes: News Reader, Chart Library, Chart Curator, Content Composer, House View

INT4.2 No page crashes
- EXPECTED: Each page loads without Python exceptions

### INT5 — Data Integrity

INT5.1 All catalogs valid JSON
- Run: python -c "import json; [json.load(open(f)) for f in ['catalogs/feeds.json','catalogs/charts.json','catalogs/news.json','catalogs/content_pieces.json','catalogs/house_view.json']]; print('All valid')"
- EXPECTED: "All valid"

INT5.2 No Streamlit in data modules
- Run: grep -rn "import streamlit" modules/config/content_catalog.py modules/config/house_view_catalog.py
- EXPECTED: No matches

---

## Summary

After running all tests, produce a table:

| Test ID | Description | Result | Notes |
|---------|-------------|--------|-------|
| DL1.1 | Content pieces catalog exists | PASS/FAIL | |
| DL1.2 | CRUD module exists | PASS/FAIL | |
| ... | ... | ... | |

List any FAIL results with details on what needs to be fixed.
