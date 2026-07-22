# EcoSort Learning Design System

> Category: Education & Sustainability

EcoSort is a friendly learning station where children classify physical waste with help from a camera and AI. The interface must feel encouraging, obvious, and safe while keeping technical status visible to teachers.

## Visual direction

Use a warm, friendly product surface with rounded shapes, generous whitespace, sturdy controls, and a single leaf-green brand accent. The experience should feel like a classroom activity rather than an engineering dashboard. A quiet, pre-rendered clay diorama may sit behind the product surfaces, while the EcoBot mascot supports welcome and guidance moments. Keep the center visually calm so the photographed object, waste-bin colors, and feedback state remain the focus.

## Color roles

- Canvas `#F2F6F0` is a quiet warm green-gray that reduces glare.
- Surface `#FFFFFF` holds primary tasks and content.
- Accent `#138A57` identifies the brand, main actions, focus, and progress.
- Ink `#13251C` is the default text color; secondary ink `#5B6C62` supports descriptions.
- Green, yellow, and red are reserved for correct/recyclable, remaining waste, and hazardous/error semantics. They are never used as arbitrary decoration.
- Text and controls must maintain WCAG AA contrast against their surfaces.

## Typography

Use Outfit for both display and body copy because its rounded geometry is friendly while remaining legible in Vietnamese. Use the scale `12 / 14 / 16 / 18 / 24 / 32 / 44` px. Headings are bold and balanced; body copy is regular or semibold and kept to readable line lengths. Numeric score data uses tabular figures.

## Spacing and layout

Use a four-pixel base spacing system with named steps from 4 to 48 px. Desktop layout gives the camera a stable support column and the learning task the larger primary column. Mobile layout stacks camera before the activity so the physical workflow remains chronological. Prefer whitespace and grouping before adding borders or shadows.

## Shape and elevation

Use 10 px for compact controls, 16 px for common controls, 24 px for cards, and a pill radius only for statuses. Surfaces use a quiet one-pixel border. Use the small elevation for utility cards and the raised elevation only for the main activity, dialogs, and floating teacher controls.

## Clay world layer

- World artwork is decorative, pre-rendered, and never connected to the webcam or recognition pipeline.
- Place scenery at the viewport edges and preserve a quiet center behind the primary task.
- Use a translucent surface token without backdrop blur so copy and controls keep reliable contrast.
- Mascots use empty alternative text and ignore pointer input. Do not let them cover controls or detected objects.
- Keep the large backdrop static. A small mascot may float using transform only, runs only while visible, and stops under reduced-motion preferences.

## Components and states

- Primary actions use the accent background, white label, strong focus ring, and a small pressed offset.
- Cards have consistent padding, border, radius, and hierarchy: step label, title, supporting content.
- Status pills pair a colored dot with literal text; color is never the only signal.
- Waste-bin choices remain large touch targets and use the real bin colors because color has domain meaning.
- Loading states explain what is happening near the camera or AI action.
- Empty and waiting states provide one clear next action.

## Motion and feedback

Motion is functional and brief. Interaction feedback is at most 160 ms and uses transform or opacity. The camera scan line and waiting indicator may loop only while the related operation is active. Respect `prefers-reduced-motion`. Success feedback may celebrate, but must never delay the next task or obscure the identified object.

## Accessibility

All controls must be keyboard reachable and have visible focus. Icon-only buttons require accessible labels. Touch targets should be at least 44 px. Use semantic headings, live regions for game-state changes, explicit input labels, and text alongside every status color. Never rely only on sound, emoji, or color to convey a result.

## Voice and microcopy

Write Vietnamese in short, positive, action-led sentences. Address children warmly without being babyish. Describe technical errors in plain language and put recovery instructions next to the failed action. Teacher-only configuration can use precise technical terms such as ESP32, RFID, API, and model threshold.

## Anti-patterns

- Do not use gradients, glow effects, excessive shadows, or unrelated accent colors.
- Do not make the camera larger than the learning task on desktop.
- Do not expose configuration fields in the child-facing primary flow.
- Do not use long paragraphs during active play.
- Do not use playful styling to hide unclear hierarchy or weak contrast.
- Do not create new raw color, radius, spacing, shadow, or motion values when a token already exists.
