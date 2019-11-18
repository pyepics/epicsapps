--
-- PostgreSQL database dump
--

-- Dumped from database version 9.6.12
-- Dumped by pg_dump version 9.6.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: commands; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.commands (
    id integer NOT NULL,
    notes text,
    command text,
    arguments text,
    status_id integer,
    nrepeat integer,
    request_time timestamp without time zone,
    start_time timestamp without time zone,
    modify_time timestamp without time zone,
    output_value text,
    output_file text
);


ALTER TABLE public.commands OWNER TO xas_user;

--
-- Name: commands_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.commands_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.commands_id_seq OWNER TO xas_user;

--
-- Name: commands_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.commands_id_seq OWNED BY public.commands.id;


--
-- Name: config; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.config (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text
);


ALTER TABLE public.config OWNER TO xas_user;

--
-- Name: config_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.config_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.config_id_seq OWNER TO xas_user;

--
-- Name: config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.config_id_seq OWNED BY public.config.id;


--
-- Name: extrapvs; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.extrapvs (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    pvname character varying(128),
    use integer
);


ALTER TABLE public.extrapvs OWNER TO xas_user;

--
-- Name: extrapvs_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.extrapvs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.extrapvs_id_seq OWNER TO xas_user;

--
-- Name: extrapvs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.extrapvs_id_seq OWNED BY public.extrapvs.id;


--
-- Name: info; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.info (
    key text NOT NULL,
    notes text,
    value text,
    modify_time timestamp without time zone,
    create_time timestamp without time zone
);


ALTER TABLE public.info OWNER TO xas_user;

--
-- Name: instrument; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.instrument (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    show integer,
    display_order integer
);


ALTER TABLE public.instrument OWNER TO xas_user;

--
-- Name: instrument_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.instrument_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.instrument_id_seq OWNER TO xas_user;

--
-- Name: instrument_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.instrument_id_seq OWNED BY public.instrument.id;


--
-- Name: instrument_info; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.instrument_info (
    key text NOT NULL,
    value text
);


ALTER TABLE public.instrument_info OWNER TO xas_user;

--
-- Name: instrument_postcommands; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.instrument_postcommands (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    exec_order integer,
    commands_id integer,
    instrument_id integer
);


ALTER TABLE public.instrument_postcommands OWNER TO xas_user;

--
-- Name: instrument_postcommands_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.instrument_postcommands_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.instrument_postcommands_id_seq OWNER TO xas_user;

--
-- Name: instrument_postcommands_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.instrument_postcommands_id_seq OWNED BY public.instrument_postcommands.id;


--
-- Name: instrument_precommands; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.instrument_precommands (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    exec_order integer,
    commands_id integer,
    instrument_id integer
);


ALTER TABLE public.instrument_precommands OWNER TO xas_user;

--
-- Name: instrument_precommands_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.instrument_precommands_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.instrument_precommands_id_seq OWNER TO xas_user;

--
-- Name: instrument_precommands_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.instrument_precommands_id_seq OWNED BY public.instrument_precommands.id;


--
-- Name: instrument_pv; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.instrument_pv (
    id integer NOT NULL,
    instrument_id integer,
    pv_id integer,
    display_order integer
);


ALTER TABLE public.instrument_pv OWNER TO xas_user;

--
-- Name: instrument_pv_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.instrument_pv_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.instrument_pv_id_seq OWNER TO xas_user;

--
-- Name: instrument_pv_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.instrument_pv_id_seq OWNED BY public.instrument_pv.id;


--
-- Name: macros; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.macros (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    arguments text,
    text text,
    output text
);


ALTER TABLE public.macros OWNER TO xas_user;

--
-- Name: macros_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.macros_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.macros_id_seq OWNER TO xas_user;

--
-- Name: macros_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.macros_id_seq OWNED BY public.macros.id;


--
-- Name: messages; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.messages (
    id integer NOT NULL,
    text text,
    modify_time timestamp without time zone
);


ALTER TABLE public.messages OWNER TO xas_user;

--
-- Name: messages_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.messages_id_seq OWNER TO xas_user;

--
-- Name: messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.messages_id_seq OWNED BY public.messages.id;


--
-- Name: monitorvalues; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.monitorvalues (
    id integer NOT NULL,
    pv_id integer,
    value text,
    modify_time timestamp without time zone
);


ALTER TABLE public.monitorvalues OWNER TO xas_user;

--
-- Name: monitorvalues_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.monitorvalues_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.monitorvalues_id_seq OWNER TO xas_user;

--
-- Name: monitorvalues_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.monitorvalues_id_seq OWNED BY public.monitorvalues.id;


--
-- Name: position; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public."position" (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    modify_time timestamp without time zone,
    image text,
    instrument_id integer
);


ALTER TABLE public."position" OWNER TO xas_user;

--
-- Name: position_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.position_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.position_id_seq OWNER TO xas_user;

--
-- Name: position_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.position_id_seq OWNED BY public."position".id;


--
-- Name: position_pv; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.position_pv (
    id integer NOT NULL,
    notes text,
    position_id integer,
    pv_id integer,
    value text
);


ALTER TABLE public.position_pv OWNER TO xas_user;

--
-- Name: position_pv_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.position_pv_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.position_pv_id_seq OWNER TO xas_user;

--
-- Name: position_pv_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.position_pv_id_seq OWNED BY public.position_pv.id;


--
-- Name: pv; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.pv (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    pvtype_id integer,
    is_monitor integer
);


ALTER TABLE public.pv OWNER TO xas_user;

--
-- Name: pv_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.pv_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.pv_id_seq OWNER TO xas_user;

--
-- Name: pv_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.pv_id_seq OWNED BY public.pv.id;


--
-- Name: pvtype; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.pvtype (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text
);


ALTER TABLE public.pvtype OWNER TO xas_user;

--
-- Name: pvtype_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.pvtype_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.pvtype_id_seq OWNER TO xas_user;

--
-- Name: pvtype_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.pvtype_id_seq OWNED BY public.pvtype.id;


--
-- Name: scancounters; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.scancounters (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    pvname character varying(128),
    use integer
);


ALTER TABLE public.scancounters OWNER TO xas_user;

--
-- Name: scancounters_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.scancounters_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.scancounters_id_seq OWNER TO xas_user;

--
-- Name: scancounters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.scancounters_id_seq OWNED BY public.scancounters.id;


--
-- Name: scandata; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.scandata (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    pvname character varying(128),
    commands_id integer,
    data double precision[],
    units text,
    breakpoints text,
    modify_time timestamp without time zone
);


ALTER TABLE public.scandata OWNER TO xas_user;

--
-- Name: scandata_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.scandata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.scandata_id_seq OWNER TO xas_user;

--
-- Name: scandata_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.scandata_id_seq OWNED BY public.scandata.id;


--
-- Name: scandefs; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.scandefs (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    text text,
    type text,
    modify_time timestamp without time zone,
    last_used_time timestamp without time zone
);


ALTER TABLE public.scandefs OWNER TO xas_user;

--
-- Name: scandefs_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.scandefs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.scandefs_id_seq OWNER TO xas_user;

--
-- Name: scandefs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.scandefs_id_seq OWNED BY public.scandefs.id;


--
-- Name: scandetectorconfig; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.scandetectorconfig (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    kind character varying(128),
    notes text,
    text text,
    scandetectors_id integer,
    modify_time timestamp without time zone
);


ALTER TABLE public.scandetectorconfig OWNER TO xas_user;

--
-- Name: scandetectorconfig_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.scandetectorconfig_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.scandetectorconfig_id_seq OWNER TO xas_user;

--
-- Name: scandetectorconfig_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.scandetectorconfig_id_seq OWNED BY public.scandetectorconfig.id;


--
-- Name: scandetectors; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.scandetectors (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    pvname character varying(128),
    use integer,
    kind character varying(128),
    options text
);


ALTER TABLE public.scandetectors OWNER TO xas_user;

--
-- Name: scandetectors_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.scandetectors_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.scandetectors_id_seq OWNER TO xas_user;

--
-- Name: scandetectors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.scandetectors_id_seq OWNED BY public.scandetectors.id;


--
-- Name: scanpositioners; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.scanpositioners (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    use integer,
    drivepv character varying(128),
    readpv character varying(128),
    extrapvs text
);


ALTER TABLE public.scanpositioners OWNER TO xas_user;

--
-- Name: scanpositioners_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.scanpositioners_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.scanpositioners_id_seq OWNER TO xas_user;

--
-- Name: scanpositioners_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.scanpositioners_id_seq OWNED BY public.scanpositioners.id;


--
-- Name: slewscanpositioners; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.slewscanpositioners (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text,
    use integer,
    drivepv character varying(128),
    readpv character varying(128),
    extrapvs text,
    config_id integer
);


ALTER TABLE public.slewscanpositioners OWNER TO xas_user;

--
-- Name: slewscanpositioners_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.slewscanpositioners_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.slewscanpositioners_id_seq OWNER TO xas_user;

--
-- Name: slewscanpositioners_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.slewscanpositioners_id_seq OWNED BY public.slewscanpositioners.id;


--
-- Name: slewscanstatus; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.slewscanstatus (
    id integer NOT NULL,
    text text,
    modify_time timestamp without time zone
);


ALTER TABLE public.slewscanstatus OWNER TO xas_user;

--
-- Name: slewscanstatus_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.slewscanstatus_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.slewscanstatus_id_seq OWNER TO xas_user;

--
-- Name: slewscanstatus_id_seq1; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.slewscanstatus_id_seq1
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.slewscanstatus_id_seq1 OWNER TO xas_user;

--
-- Name: slewscanstatus_id_seq1; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.slewscanstatus_id_seq1 OWNED BY public.slewscanstatus.id;


--
-- Name: status; Type: TABLE; Schema: public; Owner: xas_user
--

CREATE TABLE public.status (
    id integer NOT NULL,
    name character varying(512) NOT NULL,
    notes text
);


ALTER TABLE public.status OWNER TO xas_user;

--
-- Name: status_id_seq; Type: SEQUENCE; Schema: public; Owner: xas_user
--

CREATE SEQUENCE public.status_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.status_id_seq OWNER TO xas_user;

--
-- Name: status_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: xas_user
--

ALTER SEQUENCE public.status_id_seq OWNED BY public.status.id;


--
-- Name: commands id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.commands ALTER COLUMN id SET DEFAULT nextval('public.commands_id_seq'::regclass);


--
-- Name: config id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.config ALTER COLUMN id SET DEFAULT nextval('public.config_id_seq'::regclass);


--
-- Name: extrapvs id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.extrapvs ALTER COLUMN id SET DEFAULT nextval('public.extrapvs_id_seq'::regclass);


--
-- Name: instrument id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument ALTER COLUMN id SET DEFAULT nextval('public.instrument_id_seq'::regclass);


--
-- Name: instrument_postcommands id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_postcommands ALTER COLUMN id SET DEFAULT nextval('public.instrument_postcommands_id_seq'::regclass);


--
-- Name: instrument_precommands id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_precommands ALTER COLUMN id SET DEFAULT nextval('public.instrument_precommands_id_seq'::regclass);


--
-- Name: instrument_pv id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_pv ALTER COLUMN id SET DEFAULT nextval('public.instrument_pv_id_seq'::regclass);


--
-- Name: macros id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.macros ALTER COLUMN id SET DEFAULT nextval('public.macros_id_seq'::regclass);


--
-- Name: messages id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.messages ALTER COLUMN id SET DEFAULT nextval('public.messages_id_seq'::regclass);


--
-- Name: monitorvalues id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.monitorvalues ALTER COLUMN id SET DEFAULT nextval('public.monitorvalues_id_seq'::regclass);


--
-- Name: position id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public."position" ALTER COLUMN id SET DEFAULT nextval('public.position_id_seq'::regclass);


--
-- Name: position_pv id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.position_pv ALTER COLUMN id SET DEFAULT nextval('public.position_pv_id_seq'::regclass);


--
-- Name: pv id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.pv ALTER COLUMN id SET DEFAULT nextval('public.pv_id_seq'::regclass);


--
-- Name: pvtype id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.pvtype ALTER COLUMN id SET DEFAULT nextval('public.pvtype_id_seq'::regclass);


--
-- Name: scancounters id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scancounters ALTER COLUMN id SET DEFAULT nextval('public.scancounters_id_seq'::regclass);


--
-- Name: scandata id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandata ALTER COLUMN id SET DEFAULT nextval('public.scandata_id_seq'::regclass);


--
-- Name: scandefs id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandefs ALTER COLUMN id SET DEFAULT nextval('public.scandefs_id_seq'::regclass);


--
-- Name: scandetectorconfig id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandetectorconfig ALTER COLUMN id SET DEFAULT nextval('public.scandetectorconfig_id_seq'::regclass);


--
-- Name: scandetectors id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandetectors ALTER COLUMN id SET DEFAULT nextval('public.scandetectors_id_seq'::regclass);


--
-- Name: scanpositioners id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scanpositioners ALTER COLUMN id SET DEFAULT nextval('public.scanpositioners_id_seq'::regclass);


--
-- Name: slewscanpositioners id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.slewscanpositioners ALTER COLUMN id SET DEFAULT nextval('public.slewscanpositioners_id_seq'::regclass);


--
-- Name: slewscanstatus id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.slewscanstatus ALTER COLUMN id SET DEFAULT nextval('public.slewscanstatus_id_seq1'::regclass);


--
-- Name: status id; Type: DEFAULT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.status ALTER COLUMN id SET DEFAULT nextval('public.status_id_seq'::regclass);


--
-- Name: commands commands_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.commands
    ADD CONSTRAINT commands_pkey PRIMARY KEY (id);


--
-- Name: config config_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.config
    ADD CONSTRAINT config_name_key UNIQUE (name);


--
-- Name: config config_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.config
    ADD CONSTRAINT config_pkey PRIMARY KEY (id);


--
-- Name: extrapvs extrapvs_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.extrapvs
    ADD CONSTRAINT extrapvs_name_key UNIQUE (name);


--
-- Name: extrapvs extrapvs_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.extrapvs
    ADD CONSTRAINT extrapvs_pkey PRIMARY KEY (id);


--
-- Name: info info_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.info
    ADD CONSTRAINT info_pkey PRIMARY KEY (key);


--
-- Name: instrument_info instrument_info_key_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_info
    ADD CONSTRAINT instrument_info_key_key UNIQUE (key);


--
-- Name: instrument instrument_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument
    ADD CONSTRAINT instrument_name_key UNIQUE (name);


--
-- Name: instrument instrument_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument
    ADD CONSTRAINT instrument_pkey PRIMARY KEY (id);


--
-- Name: instrument_postcommands instrument_postcommands_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_postcommands
    ADD CONSTRAINT instrument_postcommands_name_key UNIQUE (name);


--
-- Name: instrument_postcommands instrument_postcommands_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_postcommands
    ADD CONSTRAINT instrument_postcommands_pkey PRIMARY KEY (id);


--
-- Name: instrument_precommands instrument_precommands_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_precommands
    ADD CONSTRAINT instrument_precommands_name_key UNIQUE (name);


--
-- Name: instrument_precommands instrument_precommands_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_precommands
    ADD CONSTRAINT instrument_precommands_pkey PRIMARY KEY (id);


--
-- Name: instrument_pv instrument_pv_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_pv
    ADD CONSTRAINT instrument_pv_pkey PRIMARY KEY (id);


--
-- Name: macros macros_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.macros
    ADD CONSTRAINT macros_name_key UNIQUE (name);


--
-- Name: macros macros_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.macros
    ADD CONSTRAINT macros_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: monitorvalues monitorvalues_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.monitorvalues
    ADD CONSTRAINT monitorvalues_pkey PRIMARY KEY (id);


--
-- Name: position pos_inst_name; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public."position"
    ADD CONSTRAINT pos_inst_name UNIQUE (name, instrument_id);


--
-- Name: position_pv position_pv_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.position_pv
    ADD CONSTRAINT position_pv_pkey PRIMARY KEY (id);


--
-- Name: position positions_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public."position"
    ADD CONSTRAINT positions_pkey PRIMARY KEY (id);


--
-- Name: pv pv_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.pv
    ADD CONSTRAINT pv_name_key UNIQUE (name);


--
-- Name: pv pv_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.pv
    ADD CONSTRAINT pv_pkey PRIMARY KEY (id);


--
-- Name: pvtype pvtypes_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.pvtype
    ADD CONSTRAINT pvtypes_name_key UNIQUE (name);


--
-- Name: pvtype pvtypes_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.pvtype
    ADD CONSTRAINT pvtypes_pkey PRIMARY KEY (id);


--
-- Name: scancounters scancounters_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scancounters
    ADD CONSTRAINT scancounters_name_key UNIQUE (name);


--
-- Name: scancounters scancounters_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scancounters
    ADD CONSTRAINT scancounters_pkey PRIMARY KEY (id);


--
-- Name: scandata scandata_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandata
    ADD CONSTRAINT scandata_name_key UNIQUE (name);


--
-- Name: scandata scandata_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandata
    ADD CONSTRAINT scandata_pkey PRIMARY KEY (id);


--
-- Name: scandefs scandefs_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandefs
    ADD CONSTRAINT scandefs_name_key UNIQUE (name);


--
-- Name: scandefs scandefs_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandefs
    ADD CONSTRAINT scandefs_pkey PRIMARY KEY (id);


--
-- Name: scandetectorconfig scandetectorconfig_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandetectorconfig
    ADD CONSTRAINT scandetectorconfig_name_key UNIQUE (name);


--
-- Name: scandetectorconfig scandetectorconfig_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandetectorconfig
    ADD CONSTRAINT scandetectorconfig_pkey PRIMARY KEY (id);


--
-- Name: scandetectors scandetectors_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandetectors
    ADD CONSTRAINT scandetectors_name_key UNIQUE (name);


--
-- Name: scandetectors scandetectors_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandetectors
    ADD CONSTRAINT scandetectors_pkey PRIMARY KEY (id);


--
-- Name: scanpositioners scanpositioners_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scanpositioners
    ADD CONSTRAINT scanpositioners_name_key UNIQUE (name);


--
-- Name: scanpositioners scanpositioners_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scanpositioners
    ADD CONSTRAINT scanpositioners_pkey PRIMARY KEY (id);


--
-- Name: slewscanpositioners slewscanpositioners_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.slewscanpositioners
    ADD CONSTRAINT slewscanpositioners_name_key UNIQUE (name);


--
-- Name: slewscanpositioners slewscanpositioners_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.slewscanpositioners
    ADD CONSTRAINT slewscanpositioners_pkey PRIMARY KEY (id);


--
-- Name: slewscanstatus slewscanstatus_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.slewscanstatus
    ADD CONSTRAINT slewscanstatus_pkey PRIMARY KEY (id);


--
-- Name: status status_name_key; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.status
    ADD CONSTRAINT status_name_key UNIQUE (name);


--
-- Name: status status_pkey; Type: CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.status
    ADD CONSTRAINT status_pkey PRIMARY KEY (id);


--
-- Name: commands commands_status_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.commands
    ADD CONSTRAINT commands_status_id_fkey FOREIGN KEY (status_id) REFERENCES public.status(id);


--
-- Name: instrument_postcommands instrument_postcommands_commands_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_postcommands
    ADD CONSTRAINT instrument_postcommands_commands_id_fkey FOREIGN KEY (commands_id) REFERENCES public.commands(id);


--
-- Name: instrument_postcommands instrument_postcommands_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_postcommands
    ADD CONSTRAINT instrument_postcommands_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instrument(id);


--
-- Name: instrument_precommands instrument_precommands_commands_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_precommands
    ADD CONSTRAINT instrument_precommands_commands_id_fkey FOREIGN KEY (commands_id) REFERENCES public.commands(id);


--
-- Name: instrument_precommands instrument_precommands_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_precommands
    ADD CONSTRAINT instrument_precommands_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instrument(id);


--
-- Name: instrument_pv instrument_pv_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_pv
    ADD CONSTRAINT instrument_pv_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instrument(id);


--
-- Name: instrument_pv instrument_pv_pv_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.instrument_pv
    ADD CONSTRAINT instrument_pv_pv_id_fkey FOREIGN KEY (pv_id) REFERENCES public.pv(id);


--
-- Name: monitorvalues monitorvalues_pv_pv_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.monitorvalues
    ADD CONSTRAINT monitorvalues_pv_pv_id_fkey FOREIGN KEY (pv_id) REFERENCES public.pv(id);


--
-- Name: position position_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public."position"
    ADD CONSTRAINT position_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instrument(id);


--
-- Name: position_pv position_pv_positions_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.position_pv
    ADD CONSTRAINT position_pv_positions_id_fkey FOREIGN KEY (position_id) REFERENCES public."position"(id);


--
-- Name: position_pv position_pv_pv_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.position_pv
    ADD CONSTRAINT position_pv_pv_id_fkey FOREIGN KEY (pv_id) REFERENCES public.pv(id);


--
-- Name: pv pv_pvtype_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.pv
    ADD CONSTRAINT pv_pvtype_id_fkey FOREIGN KEY (pvtype_id) REFERENCES public.pvtype(id);


--
-- Name: scandata scandata_commands_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandata
    ADD CONSTRAINT scandata_commands_id_fkey FOREIGN KEY (commands_id) REFERENCES public.commands(id);


--
-- Name: scandetectorconfig scandetectorconfig_scandetectors_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.scandetectorconfig
    ADD CONSTRAINT scandetectorconfig_scandetectors_id_fkey FOREIGN KEY (scandetectors_id) REFERENCES public.scandetectors(id);


--
-- Name: slewscanpositioners slewscanpositions_config_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: xas_user
--

ALTER TABLE ONLY public.slewscanpositioners
    ADD CONSTRAINT slewscanpositions_config_id_fkey FOREIGN KEY (config_id) REFERENCES public.config(id);


--
-- PostgreSQL database dump complete
--

