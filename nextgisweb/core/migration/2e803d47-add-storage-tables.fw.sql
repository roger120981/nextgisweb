/*** {
    "revision": "2e803d47", "parents": ["2d9056c4"],
    "date": "2021-05-11T03:22:14",
    "message": "Add storage tables"
} ***/

CREATE TABLE public.core_storage_stat_delta
(
    "timestamp" timestamp without time zone NOT NULL,
    component character varying,
    kind_of_data character varying,
    resource_id integer,
    value_data_volume integer
);

CREATE TABLE public.core_storage_stat_delta_total
(
    "timestamp" timestamp without time zone NOT NULL,
    kind_of_data character varying,
    value_data_volume integer
);

CREATE TABLE public.core_storage_stat_dimension
(
    "timestamp" timestamp without time zone NOT NULL,
    component character varying,
    kind_of_data character varying,
    resource_id integer,
    value_data_volume integer
);

CREATE TABLE public.core_storage_stat_dimension_total
(
    "timestamp" timestamp without time zone NOT NULL,
    kind_of_data character varying,
    value_data_volume integer
);

CREATE FUNCTION core_storage_stat_delta_after_insert() RETURNS trigger
LANGUAGE 'plpgsql' AS $BODY$
BEGIN
    INSERT INTO core_storage_stat_delta_total ("timestamp", kind_of_data, value_data_volume)
    VALUES (NEW."timestamp", NEW.kind_of_data, NEW.value_data_volume);
    RETURN NEW;
END
$BODY$;

CREATE TRIGGER after_insert AFTER INSERT ON core_storage_stat_delta
FOR EACH ROW EXECUTE PROCEDURE core_storage_stat_delta_after_insert();
