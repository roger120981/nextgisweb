import { InputNumber } from "@nextgisweb/gui/antd";

import { FormItem } from "./_FormItem";

import type { FormItemProps } from "../type";

type InputNumberProps = Parameters<typeof InputNumber>[0];

export type NumberProps = FormItemProps<InputNumberProps> & {
    /** @deprecated move to inputProps */
    min?: InputNumberProps["min"];
    /** @deprecated move to inputProps */
    max?: InputNumberProps["max"];
};

export function Number({ min, max, inputProps, ...props }: NumberProps) {
    inputProps = inputProps ?? {};
    inputProps = { min, max, ...inputProps };
    return <FormItem inputProps={inputProps} {...props} input={InputNumber} />;
}
