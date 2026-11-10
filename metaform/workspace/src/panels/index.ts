// The panel system: zones around the graph, floating panels, the saved layout and the text sizes.
export { Dock, type DockPanel, type DockProps } from "./Dock";
export { PanelsMenu } from "./PanelsMenu";
export { BODIES, PANELS, bodyOf, type PanelBody, type PanelBodyProps, type PanelDefinition, type PanelId } from "./registry";
export { placeOf, type Layout, type Zone } from "./layout";
export { useLayout, useNarrow, type LayoutActions } from "./useLayout";
