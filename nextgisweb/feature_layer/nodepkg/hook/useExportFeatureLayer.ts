import WKT from "ol/format/WKT";
import { fromExtent } from "ol/geom/Polygon";
import { useState, useCallback } from "react";

import { errorModal } from "@nextgisweb/gui/error";
import { routeURL, request, LunkwillParam } from "@nextgisweb/pyramid/api";
import pyramidSettings from "@nextgisweb/pyramid/settings!pyramid";

interface UseExportFeatureLayerProps {
    id: number;
}

export type ExportFeatureLayerOptions = {
    extent?: number[];
    resources?: string[];
    ilike?: string;
    format?: string;
};

export function useExportFeatureLayer({ id }: UseExportFeatureLayerProps) {
    const [exportLoading, setExportLoading] = useState(false);

    const openExportPage = useCallback(
        (pageParams) => {
            const url = routeURL("resource.export.page", id);
            const params = new URLSearchParams({
                ...pageParams,
            });
            window.open(`${url}?${params.toString()}`);
        },
        [id]
    );

    const exportFeatureLayer = useCallback(
        async (values: ExportFeatureLayerOptions) => {
            const { extent, resources, ...fields } = values;
            const json: Record<string, string> = {};
            if (extent && !extent.includes(null)) {
                const wkt = new WKT().writeGeometry(fromExtent(extent));

                json.intersects = wkt;
                json.intersects_srs = String(4326);
            }
            for (const key in fields) {
                const prop = fields[key];
                if (prop !== undefined) {
                    json[key] = fields[key];
                }
            }
            const params = new URLSearchParams(json);

            const ids = id ? String(id).split(",") : resources;

            let apiUrl: string;
            if (ids.length === 1) {
                apiUrl =
                    routeURL("resource.export", ids[0]) +
                    "?" +
                    params.toString();
            } else {
                params.append("resources", ids.join(","));
                apiUrl =
                    routeURL("feature_layer.export") + "?" + params.toString();
            }

            if (pyramidSettings.lunkwill_enabled) {
                const lunkwillParam = new LunkwillParam();
                lunkwillParam.require();
                try {
                    setExportLoading(true);
                    const respUrl = await request(apiUrl, {
                        lunkwill: lunkwillParam,
                        lunkwillReturnUrl: true,
                    });
                    window.open(respUrl);
                } catch (err) {
                    errorModal(err);
                    return;
                } finally {
                    setExportLoading(false);
                }
            } else {
                window.open(apiUrl);
            }
        },
        [id]
    );

    return { exportFeatureLayer, exportLoading, openExportPage };
}