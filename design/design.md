Design
# Design System Specification: Corporate Editorial Administration



\## 1. Overview \& Creative North Star

In the world of corporate administrative portals, "clutter" is the default. This design system seeks to shatter that expectation. Our Creative North Star is \*\*"The Precision Curator."\*\*



The system moves away from the rigid, boxy templates of traditional SaaS and instead adopts a high-end editorial approach. We prioritize intentional asymmetry, vast whitespace (breathing room), and a hierarchy that guides the eye through complex data with the grace of a premium financial journal. By utilizing sophisticated layering and tonal depth, we create an environment that feels authoritative yet effortless, ensuring internal staff remain focused, efficient, and calm.



\---



\## 2. Colors \& Visual Soul

The color palette is derived from a high-contrast mechanical aesthetic: deep blacks, vibrant electric cyans, and growth-oriented greens. However, in execution, we apply these with surgical restraint.



\### Palette Strategy

\* \*\*Primary (`#006e2a`) \& Secondary (`#006875`):\*\* Used primarily for functional emphasis and brand signature.

\* \*\*Surface Tiers:\*\* We utilize the `surface-container` scale to build depth. This replaces the need for dividers and outlines.



\### The "No-Line" Rule

\*\*Explicit Instruction:\*\* 1px solid borders for sectioning are prohibited. Boundaries must be defined solely through background color shifts or subtle tonal transitions.

\* \*Implementation:\* A `surface-container-low` sidebar sitting against a `surface` main content area provides enough contrast to define the edge without visual "noise."



\### The "Glass \& Gradient" Rule

To elevate the experience, floating elements (like modals or navigation bars) should utilize \*\*Glassmorphism\*\*.

\* \*\*Token:\*\* `surface-container-lowest` + 80% opacity + `backdrop-blur(20px)`.

\* \*\*Signature Textures:\*\* For high-value CTAs, use a subtle linear gradient from `primary` to `primary\_container`. This provides a "jewel" effect that feels tactile and premium.



\---



\## 3. Typography: The Editorial Voice

Our typography balances the architectural strength of \*\*Public Sans\*\* for high-level headings with the technical precision of \*\*Inter\*\* for dense data.



\* \*\*Display \& Headlines (Public Sans):\*\* These are our "anchors." Used with generous tracking and varied weights, they establish the editorial tone. A `display-lg` heading should feel like a title in a premium magazine.

\* \*\*Body \& Labels (Inter):\*\* Chosen for its exceptional legibility at small sizes. In administrative tasks, Inter ensures that hexadecimal values, currencies, and dates are unmistakable.

\* \*\*Hierarchy as Navigation:\*\* Bold `title-sm` labels paired with light-weight `body-md` values create a scan-pattern that allows staff to find specific data points in milliseconds.



\---



\## 4. Elevation \& Depth

Depth is not a drop-shadow; it is a relationship between layers.



\### The Layering Principle

We stack the `surface-container` tiers to create a physical sense of hierarchy:

1\. \*\*Base Layer:\*\* `surface` (The foundation).

2\. \*\*Section Layer:\*\* `surface-container-low` (Grouping related content).

3\. \*\*Active Component Layer:\*\* `surface-container-lowest` (The card or input area).



\### Ambient Shadows

When a component must float (e.g., a dropdown or a "Quick Action" fab), use an \*\*Ambient Shadow\*\*:

\* \*\*Color:\*\* `on-surface` at 6% opacity.

\* \*\*Blur:\*\* 24px - 40px.

\* \*\*Offset:\*\* 8px Y-axis.

This mimics natural light rather than a digital "glow."



\### The "Ghost Border" Fallback

If a border is required for extreme accessibility cases, use a \*\*Ghost Border\*\*:

\* \*\*Token:\*\* `outline-variant` at 15% opacity. Never use 100% opaque borders.



\---



\## 5. Components



\### Buttons: The Tactile Interaction

\* \*\*Primary:\*\* Gradient of `primary` to `primary\_container`. White text. Border-radius: `md` (0.375rem).

\* \*\*Secondary:\*\* `surface-container-high` background with `on-surface` text. No border.

\* \*\*Tertiary:\*\* Ghost style; `on-surface` text with no background until hover.



\### Input Fields: The Data Entry

\* \*\*Style:\*\* Minimalist. Use `surface-container-highest` as a subtle background fill rather than a border.

\* \*\*Focus State:\*\* A 2px bottom-accent of `secondary` (`#006875`). Avoid the "blue box" focus ring; use a sophisticated underline or a subtle glow.



\### Cards \& Lists: The Information Density

\* \*\*Rule:\*\* Forbid divider lines. Use vertical spacing (16px, 24px, or 32px) to separate items.

\* \*\*Nesting:\*\* Place a `surface-container-lowest` card inside a `surface-container-low` section to create "lift."



\### Modern Administrative Additions

\* \*\*Metric Marquees:\*\* Large, high-contrast `display-sm` numbers for KPIs, using the `secondary\_fixed` color for positive trends.

\* \*\*Glass Drawers:\*\* Navigation or secondary detail panels that slide in with a 90% opacity `surface` and heavy backdrop-blur.



\---



\## 6. Do’s and Don’ts



\### Do

\* \*\*Do\*\* use intentional asymmetry. A sidebar that doesn't reach the bottom of the screen or a header that overlaps a container creates a high-end, custom feel.

\* \*\*Do\*\* prioritize the "Primary" green for success and "Secondary" cyan for action.

\* \*\*Do\*\* use `surface-bright` for highlights within data tables to guide the user's eye to the most important row.



\### Don't

\* \*\*Don't\*\* use 1px solid black or grey borders. This instantly "cheapens" the UI and makes it look like a generic framework.

\* \*\*Don't\*\* use standard "drop shadows." They create visual mud. Stick to Tonal Layering.

\* \*\*Don't\*\* overcrowd the screen. If a page feels full, increase the `surface` whitespace. In high-end design, space is luxury.

\* \*\*Don't\*\* use purely "flat" design. Use the gradients and glass effects to give the portal "soul."



\---



\## 7. Token Reference Summary

\* \*\*Main Background:\*\* `surface` (#fcf9f8)

\* \*\*Content Containers:\*\* `surface-container-low` (#f6f3f2)

\* \*\*High-Priority Cards:\*\* `surface-container-lowest` (#ffffff)

\* \*\*Primary Accent:\*\* `primary` (#006e2a)

\* \*\*Interactive Accent:\*\* `secondary` (#006875)

\* \*\*Corner Radius:\*\* `DEFAULT` (0.25rem) for technical components; `xl` (0.75rem) for containers.

