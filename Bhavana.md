---

## Key Responsibilities (This Repo)

- [ ] EPD API integration (search + PDF download)- pip install aecdata 
- [ ] PDF parsing pipeline (structured data extraction from EPD documents)
- [ ] Rule-based material unit parser (kg vs. per-unit logic)
- [ ] Embodied carbon calculation engine (surface area × carbon factor)
- [ ] Ranking algorithm (by geography + carbon value)
- [ ] Material Comparative Table generation
- [ ] Report generation

---

## Tech Context

- Inputs received: surface type, area/volume (from massing model stage)
- Outputs produced: ranked material options, comparative table, downloadable report
- External APIs: EPD database API
- File handling: PDF download and parsing
- This module runs **per material category** and is designed to be called iteratively for each surface of the building