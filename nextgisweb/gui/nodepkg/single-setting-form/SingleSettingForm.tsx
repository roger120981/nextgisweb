import { useEffect, useState } from "react";

import { Input, message, Space } from "@nextgisweb/gui/antd";
import { LoadingWrapper, SaveButton } from "@nextgisweb/gui/component";
import { errorModal } from "@nextgisweb/gui/error";
import { route } from "@nextgisweb/pyramid/api";
import { useRouteGet } from "@nextgisweb/pyramid/hook/useRouteGet";
import { gettext } from "@nextgisweb/pyramid/i18n";

import type { RouteName } from "@nextgisweb/pyramid/api/type";
import type { ApiError } from "../error/type";
import type { ParamsOf } from "../type";

type InputParams = ParamsOf<typeof Input>;

interface SingleSettingFormParams {
    model: RouteName;
    settingName?: string;
    saveSuccessText?: string;
    saveSuccessReloadText?: string;
    inputProps?: InputParams;
}

const msgSaved = gettext("The setting is saved.");
const msgReload = gettext("Reload the page to get them applied.");

export function SingleSettingForm({
    model,
    settingName,
    saveSuccessText: saveSuccesText = msgSaved,
    saveSuccessReloadText: saveSuccesReloadText = msgReload,
    inputProps = {},
}: SingleSettingFormParams) {
    const [status, setStatus] = useState<"loading" | "saving" | null>(
        "loading"
    );
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [value, setValue] = useState<any>();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { data } = useRouteGet<any>({
        name: model,
    });

    useEffect(() => {
        if (data !== undefined) {
            const val = settingName ? data[settingName] : data;
            setValue(val);
            setStatus(null);
        }
    }, [data, settingName]);

    const save = async () => {
        setStatus("saving");
        try {
            const json = settingName
                ? { [settingName]: value || null }
                : value || null;
            await route(model).put({
                json,
            });
            if (saveSuccesText) {
                message.success(
                    [saveSuccesText, saveSuccesReloadText]
                        .filter(Boolean)
                        .join(" ")
                );
            }
        } catch (err) {
            errorModal(err as ApiError);
        } finally {
            setStatus(null);
        }
    };

    if (status === "loading") {
        return <LoadingWrapper rows={1} />;
    }

    return (
        <Space.Compact style={{ "width": "100%" }}>
            <Input
                value={value}
                onChange={(e) => setValue(e.target.value)}
                allowClear
                {...inputProps}
            />
            <SaveButton loading={status === "saving"} onClick={save} />
        </Space.Compact>
    );
}
