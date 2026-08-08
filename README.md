# Karen Worrall — website

Design prototypes for a new website merging two existing sites:

- **cruiseshipkaren.com** — cruise blog
- **karenworrall.co.uk** — writing portfolio

## Live prototypes

https://karenworrall.github.io/website/

## Where things stand

We are in the design and prototype phase. These pages are plain HTML and CSS so
that every change is visible immediately, with no build step in the way. They
are about layout, tone and feel — the words are placeholders.

Astro comes later. The design work done here carries straight over.

## How it works

- `index.html` — the front door to the prototypes; links to every page as it is built
- `assets/css/site.css` — the shared design foundation: colours, type, spacing, components
- `.github/workflows/deploy-pages.yml` — publishes to GitHub Pages on every push

## Design language

Carried over from the [talks site](https://karenworrall.github.io/talks/).

| Token | Value | Use |
| --- | --- | --- |
| Sea deep | `#073b4c` | Headings, dark backgrounds |
| Sea mid | `#0a5c6e` | Section labels |
| Lagoon | `#118ab2` | Links, hover states |
| Turquoise | `#06d6a0` | Highlights |
| Gold | `#c8a24b` | Hairline accents |
| Shell | `#fdfcf9` | Page background |
| Ink | `#10333c` | Body text |

Type: **Cormorant Garamond** for headings, **Jost** for body.
