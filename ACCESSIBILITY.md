# AutoAttend accessibility improvements

This pass targets common WCAG 2.2 AA patterns but **does not establish WCAG conformance**. A manual audit with keyboard and assistive technologies is still required.

## Changes

- Skip-to-content link and primary navigation accessible name.
- `aria-current="page"` for active navigation links.
- Explicit, highly visible keyboard focus styling.
- Screen-reader-friendly status announcements for meaningful scan outcomes; repetitive no-face and no-match updates are not announced every second.
- Accessible names for live camera previews and attendance feedback regions.
- Registration form heading is focused when first revealed after a new face.
- Accessible table captions, column scopes and keyboard-focusable horizontal-scroll regions.
- Reduced motion support.
- More readable secondary text color.

## Manual verification checklist

1. Use **Tab** and **Shift+Tab** from login through all role-authorized pages. Confirm all actions work with Enter/Space and keyboard focus remains visible.
2. On every page, press Tab first: **Skip to main content** should appear and focus the content when activated.
3. With NVDA + Firefox (or VoiceOver + Safari), check navigation names, form labels, table headers, error alerts and successful registration announcement.
4. Start and stop camera scans. Confirm periodic empty scan frames do **not** create nonstop spoken announcements.
5. Increase browser zoom to 200% and 400%. Check for clipped content and unreachable controls.
6. Check high contrast / forced colors and reduced-motion operating-system settings.
7. Use axe DevTools or Lighthouse on the rendered login, setup, dashboard, maintenance, working and attendance pages. Fix findings and repeat.
8. Confirm accessible workflows for users who cannot provide a camera face scan; a non-biometric alternative may be required for equitable use.

## Scope / important caveats

- No backend face recognition, database, permission or pytest code changed.
- Contrast was improved for dim text, but all foreground/background combinations still need measurement.
- Some live-updating dashboard content is not announced by screen readers to avoid noisy updates; evaluate key workflow requirements with users.
- The teacher role still lacks full class-scoped attendance UI. That is separate role functionality, not addressed here.
