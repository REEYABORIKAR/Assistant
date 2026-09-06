# UI DESIGN SPECIFICATION

## Visual source

The files in docs/ui/ are the visual references.

Recreate them as functional interfaces.

Do not use the images as static backgrounds.

---

# DESIGN SYSTEM

## Colors

Primary background:
deep navy

Secondary:
dark blue

Accent:
electric blue

Secondary accent:
cyan

Optional:
subtle purple

Avoid excessive neon.

---

# COMPONENT STYLE

Cards:

- rounded
- translucent
- subtle border
- subtle glow
- dark glass surface

Buttons:

- rounded
- clear hover state
- clear disabled state
- loading state
- keyboard accessible

Inputs:

- dark surface
- visible focus state
- clear placeholder
- validation feedback

---

# PRIMARY LAYOUT

LEFT SIDEBAR
+
CENTRAL CHAT
+
OPTIONAL CONTEXT PANEL

The central chat must dominate the interface.

---

# CHAT INPUT

Include:

+

Attach

Text input

Voice architecture

Send

The + menu:

Upload File
Add Project
Connect Source
Generate Document
Analyze Requirements
Create Workflow
Search Knowledge
Create Jira Issue

Only show permitted actions.

---

# CHAT RESPONSE TYPES

The AI can return:

- markdown
- tables
- cards
- workflow status
- risk cards
- validation cards
- document previews
- citations
- action buttons
- downloadable files

---

# REALTIME

Use streaming for:

- chat
- workflow status
- document generation

Do not fake typing or progress.

---

# STATES

Every page must have:

- loading
- empty
- error
- success
- permission denied
- not found

---

# RESPONSIVE

Desktop-first.

Must remain usable on:

- desktop
- laptop
- tablet

Mobile can be simplified but must not break.