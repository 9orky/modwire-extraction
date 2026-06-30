export const a = 1, b = 2;

export const typed: (value: string) => string = (value: string) => value.trim();

export const generic = <T>(value: T): T => value;

export const destructured = ({ id }: { id: string }) => id.toUpperCase();

export default () => typed('default');

export const handlers = {
    inline: () => typed('inline'),
    method(value: string) {
        return generic(value);
    },
    nested: {
        run: function (value: string) {
            return destructured({ id: value });
        },
    },
};

export class CallableFields {
    handler = (value: string) => typed(value);
}
