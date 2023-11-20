import debounce from "lodash-es/debounce";
import Map from "ol/Map";
import type OlMap from "ol/Map";
import View from "ol/View";
import { defaults as defaultInteractions } from "ol/interaction";
import { useEffect, useRef, useState } from "react";

import MapScaleControl from "../ol/ol-ext/ol-mapscale";
import type { DojoDisplay } from "../type";

import { buildPrintStyle } from "./PrintMapStyle";

import "./PrintMap.less";

const setMapScale = (scale: number, olMap: OlMap): void => {
    const view = olMap.getView();
    const center = view.getCenter();
    if (!center) {
        return;
    }
    const cosh = (value: number) => {
        return (Math.exp(value) + Math.exp(-value)) / 2;
    };
    const pointResolution3857 = cosh(center[1] / 6378137);
    const resolution = pointResolution3857 * (scale / (96 * 39.3701));
    olMap.getView().setResolution(resolution);
};

const buildMap = (
    container: HTMLElement,
    display: DojoDisplay,
    onScaleChange: (scale: number) => void
): [OlMap, MapScaleControl] => {
    const interactions = defaultInteractions({
        doubleClickZoom: true,
        keyboard: true,
        mouseWheelZoom: true,
        shiftDragZoom: false,
    });

    const view = new View({
        center: display.map.olMap.getView().getCenter(),
        zoom: display.map.olMap.getView().getZoom(),
    });

    const printMap: OlMap = new Map({
        target: container,
        controls: [],
        interactions,
        view,
    });

    const onChangeScale = debounce((scale) => {
        onScaleChange(scale);
    }, 100);

    const mapScale = new MapScaleControl({
        formatNumber: (scale) => {
            return String(Math.round(scale / 1000) * 1000);
        },
        onChangeScale,
    });
    printMap.addControl(mapScale);

    display.map.olMap
        .getLayers()
        .getArray()
        .forEach((layer) => {
            if (layer.getVisible() && (layer as any).printingCopy) {
                // Adding the same layer to different maps causes
                // infinite loading, thus we need a copy.
                printMap.addLayer((layer as any).printingCopy());
            }
        });

    display.map.olMap
        .getOverlays()
        .getArray()
        .forEach((overlay) => {
            if ("annPopup" in overlay && overlay.annPopup) {
                const annPopup = overlay.annPopup;
                const clonedPopup = (annPopup as any).cloneOlPopup(
                    (annPopup as any).getAnnFeature()
                );
                printMap.addOverlay(clonedPopup);
            }
        });

    const mapLogoEl = document.getElementsByClassName("map-logo");
    if (mapLogoEl.length > 0) {
        const olViewportEl = container.getElementsByClassName("ol-viewport")[0];
        const newLogoEl = mapLogoEl[0].cloneNode(true);
        olViewportEl.appendChild(newLogoEl);
    }

    return [printMap, mapScale];
};

interface PrintMapSettings {
    width: number;
    height: number;
    margin: number;
    scale: number;
    scaleLine: boolean;
    scaleValue: boolean;
}

interface PrintMapProps {
    settings: PrintMapSettings;
    display: DojoDisplay;
    onScaleChange: (scale: number) => void;
}

class PrintMapStyle {
    style: HTMLStyleElement;

    constructor() {
        this.style = document.createElement("style");
        document.body.appendChild(this.style);
    }

    private mmToPx(mm: number): number {
        // According to https://www.w3.org/TR/css3-values/#absolute-lengths
        return (mm / 10) * (96 / 2.54);
    }

    update(settings: Pick<PrintMapSettings, "width" | "height" | "margin">) {
        const widthPage = Math.round(this.mmToPx(settings.width));
        const heightPage = Math.round(this.mmToPx(settings.height));
        const margin = Math.round(this.mmToPx(settings.margin));
        const widthMap = widthPage - margin * 2;
        const heightMap = heightPage - margin * 2;

        const newStyleText = buildPrintStyle({
            widthPage,
            heightPage,
            margin,
            widthMap,
            heightMap,
        });

        this.style.innerHTML = newStyleText;
    }

    clear(): void {
        if (!this.style) {
            return;
        }
        this.style.remove();
    }
}

export const PrintMap = ({
    settings,
    display,
    onScaleChange,
}: PrintMapProps) => {
    const { width, height, margin, scale, scaleLine, scaleValue } = settings;
    const printMapRef = useRef<HTMLDivElement>(null);
    const printMap = useRef<OlMap>();
    const [mapScaleControl, setMapScaleControl] = useState<MapScaleControl>();

    const [style, setStyle] = useState<PrintMapStyle>();

    useEffect(() => {
        const printMapStyle = new PrintMapStyle();
        printMapStyle.update({ width, height, margin });
        setStyle(printMapStyle);
        return () => {
            printMapStyle.clear();
        };
    }, [width, height, margin]);

    useEffect(() => {
        if (printMapRef.current) {
            const [map, mapScale] = buildMap(
                printMapRef.current,
                display,
                onScaleChange
            );
            printMap.current = map;
            setMapScaleControl(mapScale);
        }
    }, [display]);

    useEffect(() => {
        if (printMap.current && style) {
            style.update({ width, height, margin });
            printMap.current.updateSize();
            if (scale !== undefined) {
                setMapScale(scale, printMap.current);
            }
        }
    }, [width, height, margin, scale, style]);

    useEffect(() => {
        const control = mapScaleControl;
        if (control) {
            control.setScaleLineVisibility(scaleLine);
            control.setScaleValueVisibility(scaleValue);
        }
    }, [scaleLine, scaleValue, mapScaleControl]);

    return (
        <div className="print-map-page-wrapper">
            <div className="print-map-export-wrapper">
                <div className="print-map-page">
                    <div className="print-map" ref={printMapRef}></div>
                </div>
            </div>
        </div>
    );
};