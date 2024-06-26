import type { DojoDisplay, PanelDojoItem } from "../type";

export interface TopicSubscription {
    remove: () => void;
}
export interface DojoTopic {
    subscribe: (
        type: string,
        listener: (...args: any[]) => void
    ) => TopicSubscription;
}

export interface FeatureLayerWebMapPluginConfig {
    likeSearch: boolean;
    readonly: boolean;
}

export interface DisplayItemConfig {
    plugin: Record<string, unknown>;
}

export interface PanelProps {
    display: DojoDisplay;
    close: () => void;
    title?: string;
}

export type DojoPanel = PanelDojoItem;
