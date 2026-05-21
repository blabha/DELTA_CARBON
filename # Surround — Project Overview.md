# Surround — Project Overview

## What Is This?

**Surround** is an architectural sustainability tool that helps users evaluate and compare building materials based on their **embodied carbon**, using real-world EPD (Environmental Product Declaration) data. It integrates 3D massing models, site data, surface area calculations, and carbon analysis to guide smarter material choices during the design phase.

The full workflow spans site setup → massing analysis → **material carbon analysis (this repo)** → 3D visualisation.

---

## System Architecture Overview

The system is divided into four pipeline stages, each represented by a colour-coded section in the architecture diagram:

| Stage | Colour | Scope |
|---|---|---|
| 1. Site & LCA Setup | Green | Site coordinates, surrounding model, plot area, LCA prediction |
| 2. Massing Model Analysis | Purple | Upload massing model, surface/volume recognition, area extraction |
| **3. Material Carbon Analysis** | **Blue** | **EPD lookup, PDF parsing, carbon weighting, reporting — this repo** |
| 4. Visualisation | Red | Texture scraping, apply to model, Gemini API render |

---

## Stage 1 — Site & LCA Setup *(Green Box — Not This Repo)*

Handled by another team member. Inputs:
- **Building Type** (e.g., residential, commercial)
- **Site coordinates** → fetches the surrounding 3D context model
- **Plot boundary selection** → calculates plot area

Output fed into an **LCA Prediction Model** scoped to building type and total area.

---

## Stage 2 — Massing Model Analysis *(Purple Box — Not This Repo)*

Handled by another team member. Steps:
- **Upload Massing Model** → calculates building area
- **Wall, Floor & Roof Recogniser** → identifies individual surfaces
- Calculates:
  - Individual wall surface & volume
  - Individual roof surface & volume
  - Exports geometry as **OBJ → JSON**
- User selects a specific surface → outputs **Area / Volume** for that surface

---

## Stage 3 — Material Carbon Analysis *(Blue Box — This Repo)*

This is the component I am responsible for building. It receives surface area/volume data from Stage 2 and performs material research, carbon quantification, and comparative reporting.

### 3.1 User Input

The user specifies a **material category** to search (e.g., `"Wood"`).

### 3.2 EPD API — Material Search

Queries an EPD (Environmental Product Declaration) database with the following filters:
- Location / country
- Search word (material type)

Returns a list of matching products and **downloads their PDF datasheets**.

### 3.3 PDF Reader — Data Extraction

Parses each downloaded EPD PDF to extract:
1. **Product name**
2. **Embodied carbon** (kg CO₂e per kg/unit)
3. **Company name**
4. **Location**
5. **Other relevant notes**

### 3.4 Rule-Based Material Parser

Determines the correct unit of measurement for each material type:
- **Per kg** — e.g., concrete, steel
- **Per unit** — e.g., tiles, windows, bricks

This is a rule-based system that maps material categories to their appropriate measurement convention.

### 3.5 Weights & Carbon Calculation

For the specific surface selected (e.g., roof wall), calculates the **total embodied carbon** for each candidate material by combining:
- EPD carbon factor (from PDF extraction)
- Surface area / volume (from Stage 2)

Then ranks the candidates and returns the **top 5 options** filtered by:
- Closest geographic location (to minimise transport emissions)
- Lowest embodied carbon value

### 3.6 Material Comparative Table

Aggregates all results into a **Material Comparative Table** — a structured comparison of the top material options across all applied surfaces.

Triggered condition: **"When all materials applied"**

### 3.7 Generate Report

Once the comparative table is complete, generates a final **sustainability report** summarising material choices and their embodied carbon impact.

---

## Stage 4 — Visualisation *(Red Box — Not This Repo)*

Handled by another team member. Steps (runs in a loop per material):
- **Select best choice** from the comparative table
- **Scrape material texture** from the manufacturer/company website
- **Apply texture to the 3D massing model**
- Once all materials are applied → **Visualisation using Gemini API**

---

## Data Flow Summary