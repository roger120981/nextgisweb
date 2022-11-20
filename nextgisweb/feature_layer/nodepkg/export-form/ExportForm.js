import PropTypes from "prop-types";
import { LoadingWrapper, SaveButton } from "@nextgisweb/gui/component";
import { errorModal } from "@nextgisweb/gui/error";
import {
    Checkbox,
    FieldsForm,
    Form,
    Number,
    Select,
    useForm,
} from "@nextgisweb/gui/fields-form";
import { route, routeURL } from "@nextgisweb/pyramid/api";
import { useAbortController } from "@nextgisweb/pyramid/hook/useAbortController";
import i18n from "@nextgisweb/pyramid/i18n!";
import settings from "@nextgisweb/pyramid/settings!feature_layer";
import { useEffect, useState } from "react";
import { isEmpty } from "ol/extent";
import { fromExtent } from "ol/geom/Polygon";
import WKT from "ol/format/WKT";

const exportFormats = settings.export_formats;

const srsListToOptions = (srsList) => {
    return srsList.map((srs) => {
        return {
            label: srs.display_name,
            value: srs.id,
        };
    });
};

const fieldListToOptions = (fieldList) => {
    return fieldList.map((field) => {
        return {
            label: field.display_name,
            value: field.keyname,
        };
    });
};

export function ExportForm({ id }) {
    const [status, setStatus] = useState("loading");
    const { makeSignal } = useAbortController();
    const [srsOptions, setSrsOptions] = useState([]);
    const [fieldOptions, setFieldOptions] = useState([]);
    const [defaultSrs, setDefaultSrs] = useState();
    const [format, setFormat] = useState(exportFormats[0].name);
    const [fields, setFields] = useState([]);
    const [isReady, setIsReady] = useState(false);
    const form = useForm()[0];

    async function load() {
        try {
            const signal = makeSignal();
            const [srsInfo, itemInfo] = await Promise.all(
                [
                    route("spatial_ref_sys.collection"),
                    route("resource.item", id),
                ].map((r) => r.get({ signal }))
            );
            setSrsOptions(srsListToOptions(srsInfo));
            setDefaultSrs(itemInfo[itemInfo.resource.cls].srs.id);
            setFieldOptions(fieldListToOptions(itemInfo.feature_layer.fields));
        } catch (err) {
            errorModal(err);
        } finally {
            setStatus("loaded");
        }
    }

    useEffect(() => load(), []);

    useEffect(() => {
        const exportFormat = exportFormats.find((f) => f.name === format);
        const dscoCfg = (exportFormat && exportFormat.dsco_configurable) ?? [];
        const dscoFields = [];
        const dscoFieldsValues = {};
        for (const d of dscoCfg) {
            const [name, value] = d.split(":");
            dscoFields.push({
                name,
                label: name,
            });
            if (isReady) {
                dscoFieldsValues[name] = value;
            }
        }
        if (isReady && Object.keys(dscoFieldsValues).length) {
            form.setFieldsValue(dscoFieldsValues);
        }
        setFields([
            {
                name: "format",
                label: i18n.gettext("Format"),
                widget: Select,
                choices: exportFormats.map((format) => ({
                    value: format.name,
                    label: format.display_name,
                })),
            },
            ...dscoFields,
            {
                name: "srs",
                label: i18n.gettext("SRS"),
                widget: Select,
                choices: srsOptions,
            },
            {
                name: "encoding",
                label: i18n.gettext("Encoding"),
                widget: Select,
                choices: [
                    { value: "UTF-8", label: "UTF-8" },
                    { value: "CP1251", label: "Windows-1251" },
                    { value: "CP1252", label: "Windows-1252" },
                ],
            },
            {
                name: "fid",
                label: i18n.gettext("FID field"),
            },
            {
                name: "display_name",
                label: i18n.gettext(
                    "Use field display names instead of keynames"
                ),
                widget: Checkbox,
            },
            {
                name: "fields",
                label: i18n.gettext("Fields"),
                widget: Select,
                mode: "multiple",
                choices: fieldOptions,
            },
            {
                name: "zipped",
                label: i18n.gettext("Zip archive"),
                widget: Checkbox,
                disabled: !exportFormat.single_file,
            },
            {
                name: "minlon",
                label: i18n.gettext("Left, deg."),
                widget: Number,
                min: -180,
                max: +180,
            },
            {
                name: "maxlat",
                label: i18n.gettext("Top, deg."),
                widget: Number,
                min: -90,
                max: +90,
            },
            {
                name: "maxlon",
                label: i18n.gettext("Right, deg."),
                widget: Number,
                min: -180,
                max: +180,
            },
            {
                name: "minlat",
                label: i18n.gettext("Bottom, deg."),
                widget: Number,
                min: -90,
                max: +90,
            },
        ]);
    }, [srsOptions, fieldOptions, format, isReady]);

    const onChange = (e) => {
        if ("format" in e.value) {
            setFormat(e.value.format);
        }
    };

    const buildExtent = (fields) => {
        const extent = [];
        const corners = ["minlon", "minlat", "maxlon", "maxlat"];
        corners.forEach(function (corner) {
            if (fields[corner] !== undefined) {
                extent.push(fields[corner]);
            }
            delete fields[corner];
        });
        return extent.length === 4 ? extent : undefined;
    };

    const exportFeatureLayer = () => {
        const fields = form.getFieldsValue();
        const extent = buildExtent(fields);
        const params = new URLSearchParams(fields);

        if (extent !== undefined && !isEmpty(extent)) {
            params.append(
                "intersects",
                new WKT().writeGeometryText(fromExtent(extent))
            );
        }

        window.open(routeURL("resource.export", id) + "?" + params.toString());
    };

    if (status === "loading") {
        return <LoadingWrapper />;
    }

    return (
        <FieldsForm
            fields={fields}
            form={form}
            whenReady={() => {
                setIsReady(true);
            }}
            onChange={onChange}
            initialValues={{
                format,
                fields: fieldOptions.map((field) => field.value),
                srs: defaultSrs,
                fid: "ngw_id",
                encoding: "UTF-8",
                display_name: false,
                zipped: false,
            }}
            labelCol={{ span: 6 }}
        >
            <Form.Item>
                <SaveButton onClick={exportFeatureLayer} icon={null}>
                    {i18n.gettext("Save")}
                </SaveButton>
            </Form.Item>
        </FieldsForm>
    );
}

ExportForm.propTypes = {
    id: PropTypes.number,
};
