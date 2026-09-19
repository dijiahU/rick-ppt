# Official Content Add-in fixture

Source: https://github.com/OfficeDev/Office-Addin-Scripts/blob/02e062b75a2e8a79a4a720f73403f0e004e4988f/packages/office-addin-dev-settings/templates/PowerPointPresentationWithContent.pptx

Commit: `02e062b75a2e8a79a4a720f73403f0e004e4988f` (retrieved 2026-09-20).
Microsoft Office Add-in Scripts is MIT licensed. This fixture is retained without
modification for semantic package comparisons. It is not used as a user deck.

The fixture uses a content webextension in `ppt/slides/udata/data.xml`, a slide
webextension relationship, graphicFrame inside mc:Choice requiring `we pca`, an
mc:Fallback p:pic and a snapshot image relationship from the extension part.
The reference store is `developer`, type `Registry`. The reference ID denotes the
manifest add-in ID; webextension ID identifies its instance.

The fixture also contains a duplicate shape ID outside the choice branches;
our generated insertions allocate unique IDs rather than copying that defect.
