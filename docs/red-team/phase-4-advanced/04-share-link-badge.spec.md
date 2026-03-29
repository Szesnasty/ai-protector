# 04 — Share Link + README Badge

> **Layer:** Full-stack
> **Phase:** 4 (Advanced)
> **Depends on:** Results page, Export infrastructure

## Scope

Public sharing: shareable URL to results and an embeddable badge (like CI/CD badges) for security score.

## Implementation Steps

### Step 1: Share link

- Generate public URL: `https://protector.../share/run/{token}`
- Token: unique, non-guessable
- Public page shows: score, category breakdown, run metadata
- No auth required to view

### Step 2: README badge

- Endpoint: `GET /v1/badge/run/{id}` → SVG badge image
- Format: `![Security Score](https://protector.../badge/run/123)`
- Shows: "AI Protector | 84/100" with color

### Step 3: Badge customization

- Color based on score (same ranges as UI)
- Optional: style parameter (flat, flat-square, for-the-badge)

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_share_link_generates` | Token generated, URL accessible |
| `test_share_page_public` | No auth needed to view |
| `test_badge_svg_renders` | Valid SVG with score |
| `test_badge_color_correct` | Color matches score range |

## Definition of Done

- [ ] Share link generates and works publicly
- [ ] Badge SVG renders with correct score and color
- [ ] Embeddable in README/docs
- [ ] All tests pass
