# Inherited presentation styling

Slide → slideLayout → slideMaster → theme are relationship dependencies. Placeholders inherit by type/index; missing local coordinates or font values can be intentional inheritance. Resolve the chain before adding explicit overrides.

Masters, layouts, themes, presentation.xml and Content_Types are high-risk shared files. Snapshot before editing if hooks are not active. A change can affect every slide, so render the full deck. Prefer a local shape override when the request applies to one object. Preserve layout/master relationship cycles; cycles are normal, not corruption.
