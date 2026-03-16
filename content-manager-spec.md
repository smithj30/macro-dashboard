# Content Manager (Module 3) — Functional Specification

> Part of the Macro Dashboard central hub (BigPicture vision)
> Written: 2026-03-15

---

## 1. Purpose

A content composition tool for turning macro research into polished communications. The module pulls charts from the Chart Library (both News Reader and Module 2 data-driven charts) and lets the user assemble them with commentary into output formats: email updates, the House View document, and presentation decks.

This is NOT a general-purpose document editor. It is a **chart-first composition tool** — the user picks visuals, adds commentary, and exports. The heavy lifting of chart curation has already happened in the News Reader and Chart Curator.

---

## 2. Design Principles

- **Chart-first workflow**: Start by selecting charts, then add commentary. Not the other way around.
- **AI-drafted commentary**: When charts are selected, offer AI-generated bullet points as a starting draft. The user edits from there.
- **Multiple output formats from one composition**: A single "content piece" can be exported as an email, a slide, a PDF, or a House View entry — the source material is the same.
- **Living documents**: The House View is not a one-time export. It lives in the app and is continuously revised.
- **Shared data layer**: Charts come from the Chart Library (catalogs/news.json chart_images + catalogs/charts.json). Tags are from the shared vocabulary.

---

## 3. Output Formats

### 3.1 Quick Email Update (highest frequency)

**Structure**: 2-4 charts arranged in a grid, with 2-5 bullet points of commentary. Branded with Kennedy Lewis header/footer.

**Output**: Formatted HTML that can be copy-pasted into Outlook, or sent directly via Gmail API.

**Template**:
```
┌─────────────────────────────────────┐
│  KL Header Bar                      │
├─────────────────────────────────────┤
│                                     │
│  Subject / Title                    │
│                                     │
│  • Bullet commentary point 1       │
│  • Bullet commentary point 2       │
│  • Bullet commentary point 3       │
│                                     │
│  ┌──────────┐  ┌──────────┐        │
│  │  Chart 1 │  │  Chart 2 │        │
│  │          │  │          │        │
│  └──────────┘  └──────────┘        │
│  Caption 1      Caption 2          │
│                                     │
│  ┌──────────┐  ┌──────────┐        │
│  │  Chart 3 │  │  Chart 4 │        │
│  │          │  │          │        │
│  └──────────┘  └──────────┘        │
│  Caption 3      Caption 4          │
│                                     │
├─────────────────────────────────────┤
│  KL Footer (disclaimer, contact)    │
└─────────────────────────────────────┘
```

### 3.2 House View (second highest frequency)

**Structure**: A single living document — one-page summary of bullets organized by macro theme, reflecting the firm's current views. Updated continuously, not created from scratch each time.

**Stored in**: `catalogs/house_view.json` — a structured document, not a flat text file.

**Schema**:
```json
{
  "title": "Kennedy Lewis — House View",
  "last_updated": "2026-03-15T14:00:00Z",
  "updated_by": "Josh",
  "sections": [
    {
      "theme": "rates",
      "title": "Rates & Monetary Policy",
      "bullets": [
        {
          "text": "Fed likely on hold through H1 2026; market pricing has converged to our view",
          "updated_at": "2026-03-15T14:00:00Z",
          "supporting_charts": ["chrt_abc123", "item_def456"]
        },
        {
          "text": "Long end remains range-bound; 10Y likely 4.0-4.5% near term",
          "updated_at": "2026-03-10T09:00:00Z",
          "supporting_charts": []
        }
      ]
    },
    {
      "theme": "credit",
      "title": "Credit Markets",
      "bullets": [...]
    },
    {
      "theme": "labor",
      "title": "Labor Market",
      "bullets": [...]
    }
  ]
}
```

**Output**: Exportable as a formatted one-page PDF or Word doc with KL branding. Also viewable and editable directly in the app.

### 3.3 Monday Presentation Deck (already built)

This is the WeeklyMacro pipeline output. The Content Manager does NOT rebuild this — the Chart Curator and macro_build_deck.js handle it. The Content Manager's role is:
- Browse past decks
- Pull individual slides or charts from past decks into other content pieces
- Optionally trigger the deck build from within the app (already available in Chart Curator)

### 3.4 LP Marketing Deck (lower frequency)

**Structure**: More polished than the Monday deck. Charts with citations, longer commentary, professional layout. Typically 10-20 slides.

**Output**: PPTX file using macro_build_deck.js with a different template/style flag, or a separate builder with LP-specific formatting.

**Deferred to Phase 3** — the slide builder infrastructure needs to exist first.

### 3.5 Email Distribution — External (lower frequency)

**Structure**: Similar to quick email update but more polished. Longer commentary, multiple sections, formal tone. Branded with KL logo and disclaimer.

**Output**: Formatted HTML email. Can reuse the email template from 3.1 with additional sections.

### 3.6 LinkedIn Post (lowest frequency)

**Structure**: Short text (1-3 paragraphs) with 1-2 charts as images. Optimized for LinkedIn's format.

**Output**: Text for copy-paste + chart images downloaded for upload to LinkedIn.

**Deferred to Phase 4.**

---

## 4. Data Model

### 4.1 Content Piece

A content piece is a draft composition that can be exported to one or more formats. Stored in `catalogs/content_pieces.json`.

```json
{
  "id": "cp_a1b2c3d4",
  "title": "Rates Update — March 15",
  "type": "email_update",
  "status": "draft",
  "created_at": "2026-03-15T14:00:00Z",
  "updated_at": "2026-03-15T14:30:00Z",
  "tags": ["rates", "monetary-policy"],
  "charts": [
    {
      "chart_ref": "chrt_e5f6g7h8",
      "source": "news_reader",
      "caption": "Market Implied Rate Cuts",
      "position": 1
    },
    {
      "chart_ref": "item_abc123",
      "source": "dashboard",
      "caption": "Fed Funds Rate vs. 2Y Treasury",
      "position": 2
    }
  ],
  "commentary": [
    {
      "text": "Markets have repriced significantly — now pricing fewer than 2 cuts in 2026",
      "ai_generated": true,
      "edited": true
    },
    {
      "text": "Our view remains that the Fed is on hold through H1",
      "ai_generated": false,
      "edited": false
    }
  ],
  "export_history": [
    {
      "format": "email_html",
      "exported_at": "2026-03-15T15:00:00Z",
      "recipient": "internal"
    }
  ]
}
```

**Type values**: `email_update`, `email_distribution`, `house_view_entry`, `lp_deck`, `linkedin_post`

**Status values**: `draft`, `ready`, `sent`, `archived`

### 4.2 Chart Reference

Charts in a content piece can come from two sources:
- **News Reader charts**: referenced by `chrt_` ID from catalogs/news.json chart_images
- **Dashboard charts**: referenced by `item_` ID from catalogs/charts.json (these are Plotly charts that get rendered to PNG for inclusion)

The `source` field indicates which catalog to look up. For dashboard charts, the app renders the Plotly figure to a PNG at export time.

---

## 5. Views & User Workflows

### 5.1 Sidebar Navigation

```
📊 Macro Dashboard
─────────────────
[Dashboard Viewer ▼]
─────────────────
🔍 Data Explorer
📋 Feed Manager
📈 Chart Editor
🖥️ Dashboard Builder
─────────────────
📰 News Reader
🖼️ Chart Library
🎯 Chart Curator
─────────────────
✏️ Content Composer      ← NEW
📄 House View            ← NEW
📂 Content Archive       ← NEW
─────────────────
🏷️ Tag Manager
⚙️ Settings
```

### 5.2 Content Composer (`views/content_composer.py`)

**Purpose**: Create and edit content pieces. The main authoring view.

**Workflow**:

**Step 1 — Start a new piece or open a draft**:
- "New Content" button with type selector (Email Update, Email Distribution, LinkedIn Post)
- List of existing drafts with title, type, date, chart count
- Click a draft to resume editing

**Step 2 — Select charts**:
- Opens a **chart picker** panel (reuse the Chart Library grid with filters)
- Two source tabs: "News Reader Charts" and "Dashboard Charts"
- News Reader tab: shows chart_images from catalogs/news.json with tag/source/date filters
- Dashboard tab: shows charts from catalogs/charts.json with tag filters. These are live Plotly charts — show a rendered thumbnail preview.
- Select charts by clicking. Selected charts appear in a "Selected" strip at the bottom with drag-to-reorder.
- "Done Selecting" button closes the picker and returns to the composer.

**Step 3 — Add commentary**:
- Left side: selected charts displayed in a 2-column grid with captions (editable)
- Right side: commentary editor
  - "Generate Draft" button: sends the selected charts (as images) and their captions to Claude API, asks for 3-5 analytical bullet points. Returns AI-drafted text.
  - Bullet list: each bullet is an editable text input. Add/remove/reorder bullets.
  - Each bullet has an "AI generated" badge if it came from the draft. Badge disappears once edited.
- Title field at the top (editable)
- Tag picker

**Step 4 — Preview and export**:
- "Preview" tab shows the composed content in its output format (HTML email layout, etc.)
- Export buttons:
  - "Copy HTML" — copies formatted HTML to clipboard for pasting into Outlook
  - "Send via Gmail" — sends directly via Gmail API (uses same credentials as gmail_fetch.py)
  - "Download as PDF" — renders to PDF
  - "Save Draft" — saves to catalogs/content_pieces.json

### 5.3 House View (`views/house_view.py`)

**Purpose**: Maintain the firm's living macro view document.

**Layout**:
```
┌──────────────────────────────────────────────────────────┐
│  House View                    Last updated: Mar 15, 2026│
│                                [Export PDF] [Export Word] │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  RATES & MONETARY POLICY                    [+ Add Bullet]│
│  ─────────────────────────────────────────               │
│  • Fed likely on hold through H1 2026      [edit] [📊] [x]│
│    Updated: Mar 15 | Charts: 2                           │
│  • Long end range-bound 4.0-4.5%           [edit] [📊] [x]│
│    Updated: Mar 10 | Charts: 0                           │
│                                                          │
│  CREDIT MARKETS                             [+ Add Bullet]│
│  ─────────────────────────────────────────               │
│  • Spreads tight but technicals supportive [edit] [📊] [x]│
│    Updated: Mar 12 | Charts: 1                           │
│                                                          │
│  LABOR MARKET                               [+ Add Bullet]│
│  ─────────────────────────────────────────               │
│  • (no bullets yet)                        [+ Add Bullet]│
│                                                          │
│  [+ Add Section]                                         │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Behavior**:
- Sections are organized by macro theme (from the tag vocabulary)
- Each bullet is editable inline — click "edit" to toggle to a text input
- [📊] button on each bullet opens a mini chart picker to attach supporting charts. These charts appear as small thumbnails next to the bullet when viewing.
- "Updated" timestamp auto-updates when a bullet is edited
- [+ Add Section] creates a new theme section
- [+ Add Bullet] adds a blank bullet to a section
- Drag to reorder bullets within a section, or sections within the document
- "Generate AI Update" button: sends the current House View + recent News Reader content to Claude, asks it to suggest updates or new bullets based on recent data. Suggestions appear as pending additions the user can accept or dismiss.
- All changes save automatically to catalogs/house_view.json

**Export**:
- "Export PDF" — renders the House View as a one-page branded PDF
- "Export Word" — renders as a branded Word doc
- The export includes the title, date, all sections and bullets. Supporting charts are optionally included as small thumbnails next to their bullets.

### 5.4 Content Archive (`views/content_archive.py`)

**Purpose**: Browse and search past content pieces.

**Layout**: Simple list/table of all content pieces from catalogs/content_pieces.json. Filterable by type, date range, tags, status. Click to view or resume editing. Shows export history (when it was sent, to whom).

---

## 6. AI Integration

### 6.1 Commentary Generation

When the user clicks "Generate Draft" in the Content Composer:

1. Collect all selected charts (images + captions)
2. Send to Claude API with a prompt:
   ```
   You are a macro research analyst at Kennedy Lewis Investment Management.
   Given the following charts and their captions, write 3-5 concise analytical
   bullet points summarizing the key takeaways. Be specific about data points
   visible in the charts. Use a professional but direct tone.
   
   Charts:
   [chart images + captions]
   ```
3. Parse the response into individual bullet strings
4. Populate the commentary editor with the AI-drafted bullets

### 6.2 House View Update Suggestions

When the user clicks "Generate AI Update" in the House View:

1. Send the current House View content + the last 7 days of News Reader content items (titles, previews, chart captions) to Claude
2. Prompt asks: "Based on the recent research content below, suggest updates to the House View. For each suggestion, specify which section it belongs to and whether it's a new bullet or an update to an existing one."
3. Display suggestions as pending items the user can accept, edit, or dismiss

### 6.3 Email Subject Line Generation

When exporting an email update, offer an AI-generated subject line based on the charts and commentary.

---

## 7. Email Export

### 7.1 HTML Email Template

The email HTML template should:
- Use inline CSS (email clients strip stylesheets)
- Include KL branded header bar (Harbor Depth #011E2F background, white text)
- Charts rendered as inline images (base64 encoded or CID-attached)
- Bullets in clean HTML list format
- KL footer with disclaimer text
- Be tested in Outlook rendering (avoid CSS grid, flexbox — use tables for layout)

### 7.2 Gmail Send Integration

Reuse the Gmail API credentials from scripts/gmail_fetch.py:
- Read credentials path from config/app_config.yaml
- Compose a MIME message with HTML body and inline chart images
- Send via Gmail API (requires gmail.send scope — may need to re-authorize with additional scope)
- Log the send in the content piece's export_history

---

## 8. Implementation Phases

### Phase 1: Foundation
- Content piece data model and CRUD (catalogs/content_pieces.json, modules/config/content_catalog.py)
- House View data model and CRUD (catalogs/house_view.json)
- Chart picker component that browses both News Reader and Dashboard charts
- Content Composer view: chart selection, commentary editing, save draft
- House View view: section/bullet editing, auto-save

### Phase 2: AI + Export
- AI commentary generation (Claude API)
- HTML email template with KL branding
- "Copy HTML" export for Outlook paste
- House View PDF export
- House View Word doc export
- Content Archive view

### Phase 3: Send + Polish
- Gmail send integration (requires gmail.send scope)
- AI subject line generation
- House View AI update suggestions
- Email distribution format (longer, multi-section)
- LP deck format (PPTX via macro_build_deck.js with LP template flag)

### Phase 4: Future
- LinkedIn post format
- AI-suggested content pieces based on incoming research
- Scheduled email distributions
- Version history on House View

---

## 9. Integration Points

### With Module 1 (News Reader)
- Chart picker pulls from catalogs/news.json chart_images
- News Reader "Flag for Content Use" marks charts for easy discovery in the picker
- Content pieces reference News Reader charts by chrt_ ID

### With Module 2 (Data Portal)
- Chart picker pulls from catalogs/charts.json
- Dashboard Plotly charts are rendered to PNG at export time for inclusion in emails/PDFs
- Data-driven charts carry their source attribution (FRED series, etc.)

### With WeeklyMacro Pipeline
- Monday deck remains the pipeline's job — Content Manager doesn't rebuild it
- Past deck slides/charts are browsable from the Content Archive
- Individual charts from past decks can be pulled into new content pieces via the Chart Library

### Shared Infrastructure
- Tag vocabulary (config/tags.json) used for content piece tags and House View sections
- Gmail API credentials shared between gmail_fetch.py and the send integration
- KL brand styles (chart_styles.json colors) used in email templates and PDF export
- Chart renderer (components/chart_renderer.py) renders Dashboard charts to PNG for export

---

## 10. Error Handling

| Scenario | Behavior |
|----------|----------|
| Chart reference points to deleted chart | Show placeholder with "Chart unavailable" message |
| AI commentary generation fails | Show error, let user write bullets manually |
| Gmail send fails | Show error with details, save draft so nothing is lost |
| PDF export fails | Show error, offer HTML copy as fallback |
| House View JSON corrupted | Load from backup (auto-backup before each save) |
| Dashboard chart render fails | Show error for that chart, continue with others |
| Very large email (10+ charts) | Warn about email size, suggest splitting into multiple sends |
