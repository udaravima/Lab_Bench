/*
 * labbench_can.h — CAN 2.0B frame codec for the Lab_Bench modular PSU.
 * Implements docs/03-can-protocol.md. Header-only, C99, no dependencies.
 * Shared verbatim between module (STM32G431) and manager (ESP32-S3) firmware;
 * all payloads are packed little-endian by byte access, so it is portable
 * regardless of host endianness.
 */
#ifndef LABBENCH_CAN_H
#define LABBENCH_CAN_H

#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#define LB_PROTO_VERSION 1
#define LB_NUM_SLOTS     8

/* ---- Identifier map (11-bit) ------------------------------------------- */
#define LB_ID_FAULT_BASE   0x010u /* + slot, module -> mgr, highest priority */
#define LB_ID_GLOBAL_OFF   0x020u /* mgr -> all */
#define LB_ID_GLOBAL_STATE 0x021u /* mgr -> all, 1 Hz heartbeat */
#define LB_ID_CMD_BASE     0x100u /* + slot*0x10 + cmd, mgr -> module */
#define LB_ID_STATUS_BASE  0x300u /* + slot*0x10 + typ, module -> mgr */
#define LB_ID_HELLO_BASE   0x7E0u /* + slot, module -> mgr, on boot */

typedef enum {
    LB_CMD_SET_VI    = 0,
    LB_CMD_OUTPUT    = 1,
    LB_CMD_LIMITS    = 2,
    LB_CMD_CAL_WRITE = 3,
    LB_CMD_IDENT     = 4,
    LB_CMD_RESET     = 5,
} lb_cmd_t;

typedef enum {
    LB_TYP_TELEM_VI  = 0,
    LB_TYP_TELEM_AUX = 1,
    LB_TYP_STATUS    = 2,
    LB_TYP_ENERGY    = 3,
} lb_typ_t;

/* ---- Shared enums / bitfields ------------------------------------------ */
typedef enum {
    LB_STATE_SAFE          = 0,
    LB_STATE_ACTIVE        = 1,
    LB_STATE_FAULT_LATCHED = 2,
} lb_state_t;

/* OUTPUT command modes (doc 03 §3) */
#define LB_OUT_OFF        0u
#define LB_OUT_ON         1u
#define LB_OUT_ON_DEM     2u
#define LB_OUT_ON_DROOP   3u
#define LB_OUT_ON_DEM_DRP 4u
#define LB_OUT_MODE_MAX   4u

/* Fault bits (latching; protection matrix rows in parentheses) */
#define LB_FAULT_OCP_BACKUP 0x01u /* #2  */
#define LB_FAULT_OVP_HW     0x02u /* #4  */
#define LB_FAULT_OTP        0x04u /* #12 */
#define LB_FAULT_SENSE      0x08u /* #18 */
#define LB_FAULT_REVCUR     0x10u /* #7  */

/* Warn bits (non-latching) */
#define LB_WARN_ENV_CLAMP   0x01u /* setpoint clamped to envelope (#5) */
#define LB_WARN_DERATE      0x02u /* thermal derate active (#11) */
#define LB_WARN_COMMS_LOST  0x04u /* manager heartbeat missing (#14) */

/* STATUS.mode live flags */
#define LB_MODE_OUT_ON    0x01u
#define LB_MODE_DEM       0x02u
#define LB_MODE_DROOP     0x04u
#define LB_MODE_CC_ACTIVE 0x08u

/* Comms-loss policy (LIMITS) */
#define LB_POLICY_OFF  0u
#define LB_POLICY_HOLD 1u

/* RESET magics */
#define LB_RESET_REBOOT      0xA5u
#define LB_RESET_CLEAR_FAULT 0x5Au

/* Calibration items / points (CAL_WRITE) */
typedef enum {
    LB_CAL_VSET = 0, LB_CAL_ISET = 1, LB_CAL_VMEAS = 2, LB_CAL_IMEAS = 3
} lb_cal_item_t;
typedef enum { LB_CAL_OFFSET = 0, LB_CAL_GAIN = 1 } lb_cal_point_t;

/* ---- Frame container ---------------------------------------------------- */
typedef struct {
    uint16_t id;      /* 11-bit standard identifier */
    uint8_t  dlc;
    uint8_t  data[8];
} lb_can_frame;

/* ---- Message payload structs -------------------------------------------- */
typedef struct { int32_t v_uv; int32_t i_ua; } lb_set_vi;        /* also TELEM_VI */
typedef struct {
    int32_t p_max_mw;
    int16_t t_derate_dC;   /* 0.1 degC units */
    uint8_t policy;        /* LB_POLICY_* */
} lb_limits;
typedef struct { uint8_t item, point; int32_t value; } lb_cal_write;
typedef struct {
    uint8_t state, fault, warn, mode;
    int16_t vset_echo_10mV;
    int16_t iset_echo_10mA;
} lb_status;
typedef struct { int16_t t_fet_dC, t_ind_dC; uint16_t vbus_10mV, pout_100mW; } lb_telem_aux;
typedef struct { int32_t charge_10uAh; int32_t energy_10uWh; } lb_energy;
typedef struct { uint8_t fault, warn, state; } lb_fault_msg;
typedef struct { uint8_t proto_ver, fw_major, fw_minor; uint32_t uid; } lb_hello;
typedef struct { uint16_t budget_w; uint8_t flags, seq; } lb_global_state;

/* ---- Little-endian helpers ---------------------------------------------- */
static inline void lb_wr16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static inline void lb_wr32(uint8_t *p, uint32_t v) { lb_wr16(p, (uint16_t)v); lb_wr16(p + 2, (uint16_t)(v >> 16)); }
static inline uint16_t lb_rd16(const uint8_t *p) { return (uint16_t)(p[0] | ((uint16_t)p[1] << 8)); }
static inline uint32_t lb_rd32(const uint8_t *p) { return (uint32_t)lb_rd16(p) | ((uint32_t)lb_rd16(p + 2) << 16); }

/* ---- Identifier build / parse ------------------------------------------- */
static inline uint16_t lb_id_cmd(uint8_t slot, lb_cmd_t cmd)    { return (uint16_t)(LB_ID_CMD_BASE    + slot * 0x10u + (uint16_t)cmd); }
static inline uint16_t lb_id_status(uint8_t slot, lb_typ_t typ) { return (uint16_t)(LB_ID_STATUS_BASE + slot * 0x10u + (uint16_t)typ); }
static inline uint16_t lb_id_fault(uint8_t slot)                { return (uint16_t)(LB_ID_FAULT_BASE + slot); }
static inline uint16_t lb_id_hello(uint8_t slot)                { return (uint16_t)(LB_ID_HELLO_BASE + slot); }

typedef enum {
    LB_KIND_UNKNOWN = 0, LB_KIND_FAULT, LB_KIND_GLOBAL_OFF, LB_KIND_GLOBAL_STATE,
    LB_KIND_CMD, LB_KIND_STATUS, LB_KIND_HELLO
} lb_kind_t;

/* Classify an incoming identifier; slot/sub are written when applicable
 * (sub = cmd index for LB_KIND_CMD, typ index for LB_KIND_STATUS). */
static inline lb_kind_t lb_id_parse(uint16_t id, uint8_t *slot, uint8_t *sub)
{
    if (id == LB_ID_GLOBAL_OFF)   return LB_KIND_GLOBAL_OFF;
    if (id == LB_ID_GLOBAL_STATE) return LB_KIND_GLOBAL_STATE;
    if (id >= LB_ID_FAULT_BASE && id < LB_ID_FAULT_BASE + LB_NUM_SLOTS) {
        *slot = (uint8_t)(id - LB_ID_FAULT_BASE); return LB_KIND_FAULT;
    }
    if (id >= LB_ID_HELLO_BASE && id < LB_ID_HELLO_BASE + LB_NUM_SLOTS) {
        *slot = (uint8_t)(id - LB_ID_HELLO_BASE); return LB_KIND_HELLO;
    }
    if (id >= LB_ID_CMD_BASE && id < LB_ID_CMD_BASE + LB_NUM_SLOTS * 0x10u) {
        *slot = (uint8_t)((id - LB_ID_CMD_BASE) >> 4);
        *sub  = (uint8_t)(id & 0x0Fu);
        return (*sub <= LB_CMD_RESET) ? LB_KIND_CMD : LB_KIND_UNKNOWN;
    }
    if (id >= LB_ID_STATUS_BASE && id < LB_ID_STATUS_BASE + LB_NUM_SLOTS * 0x10u) {
        *slot = (uint8_t)((id - LB_ID_STATUS_BASE) >> 4);
        *sub  = (uint8_t)(id & 0x0Fu);
        return (*sub <= LB_TYP_ENERGY) ? LB_KIND_STATUS : LB_KIND_UNKNOWN;
    }
    return LB_KIND_UNKNOWN;
}

/* ---- Encoders ------------------------------------------------------------ */
static inline void lb_enc_set_vi(lb_can_frame *f, uint8_t slot, const lb_set_vi *m)
{
    f->id = lb_id_cmd(slot, LB_CMD_SET_VI); f->dlc = 8;
    lb_wr32(f->data, (uint32_t)m->v_uv); lb_wr32(f->data + 4, (uint32_t)m->i_ua);
}
static inline void lb_enc_output(lb_can_frame *f, uint8_t slot, uint8_t mode)
{
    f->id = lb_id_cmd(slot, LB_CMD_OUTPUT); f->dlc = 1; f->data[0] = mode;
}
static inline void lb_enc_limits(lb_can_frame *f, uint8_t slot, const lb_limits *m)
{
    f->id = lb_id_cmd(slot, LB_CMD_LIMITS); f->dlc = 8;
    lb_wr32(f->data, (uint32_t)m->p_max_mw);
    lb_wr16(f->data + 4, (uint16_t)m->t_derate_dC);
    f->data[6] = m->policy; f->data[7] = 0;
}
static inline void lb_enc_cal_write(lb_can_frame *f, uint8_t slot, const lb_cal_write *m)
{
    f->id = lb_id_cmd(slot, LB_CMD_CAL_WRITE); f->dlc = 6;
    f->data[0] = m->item; f->data[1] = m->point; lb_wr32(f->data + 2, (uint32_t)m->value);
}
static inline void lb_enc_ident(lb_can_frame *f, uint8_t slot)
{
    f->id = lb_id_cmd(slot, LB_CMD_IDENT); f->dlc = 0;
}
static inline void lb_enc_reset(lb_can_frame *f, uint8_t slot, uint8_t magic)
{
    f->id = lb_id_cmd(slot, LB_CMD_RESET); f->dlc = 1; f->data[0] = magic;
}
static inline void lb_enc_global_off(lb_can_frame *f)
{
    f->id = LB_ID_GLOBAL_OFF; f->dlc = 0;
}
static inline void lb_enc_global_state(lb_can_frame *f, const lb_global_state *m)
{
    f->id = LB_ID_GLOBAL_STATE; f->dlc = 4;
    lb_wr16(f->data, m->budget_w); f->data[2] = m->flags; f->data[3] = m->seq;
}
static inline void lb_enc_telem_vi(lb_can_frame *f, uint8_t slot, const lb_set_vi *m)
{
    f->id = lb_id_status(slot, LB_TYP_TELEM_VI); f->dlc = 8;
    lb_wr32(f->data, (uint32_t)m->v_uv); lb_wr32(f->data + 4, (uint32_t)m->i_ua);
}
static inline void lb_enc_telem_aux(lb_can_frame *f, uint8_t slot, const lb_telem_aux *m)
{
    f->id = lb_id_status(slot, LB_TYP_TELEM_AUX); f->dlc = 8;
    lb_wr16(f->data, (uint16_t)m->t_fet_dC); lb_wr16(f->data + 2, (uint16_t)m->t_ind_dC);
    lb_wr16(f->data + 4, m->vbus_10mV); lb_wr16(f->data + 6, m->pout_100mW);
}
static inline void lb_enc_status(lb_can_frame *f, uint8_t slot, const lb_status *m)
{
    f->id = lb_id_status(slot, LB_TYP_STATUS); f->dlc = 8;
    f->data[0] = m->state; f->data[1] = m->fault; f->data[2] = m->warn; f->data[3] = m->mode;
    lb_wr16(f->data + 4, (uint16_t)m->vset_echo_10mV);
    lb_wr16(f->data + 6, (uint16_t)m->iset_echo_10mA);
}
static inline void lb_enc_energy(lb_can_frame *f, uint8_t slot, const lb_energy *m)
{
    f->id = lb_id_status(slot, LB_TYP_ENERGY); f->dlc = 8;
    lb_wr32(f->data, (uint32_t)m->charge_10uAh); lb_wr32(f->data + 4, (uint32_t)m->energy_10uWh);
}
static inline void lb_enc_fault(lb_can_frame *f, uint8_t slot, const lb_fault_msg *m)
{
    f->id = lb_id_fault(slot); f->dlc = 4;
    f->data[0] = m->fault; f->data[1] = m->warn; f->data[2] = m->state; f->data[3] = 0;
}
static inline void lb_enc_hello(lb_can_frame *f, uint8_t slot, const lb_hello *m)
{
    f->id = lb_id_hello(slot); f->dlc = 8;
    f->data[0] = m->proto_ver; f->data[1] = m->fw_major; f->data[2] = m->fw_minor; f->data[3] = 0;
    lb_wr32(f->data + 4, m->uid);
}

/* ---- Decoders (return false on DLC mismatch) ----------------------------- */
static inline bool lb_dec_set_vi(const lb_can_frame *f, lb_set_vi *m)
{
    if (f->dlc != 8) return false;
    m->v_uv = (int32_t)lb_rd32(f->data); m->i_ua = (int32_t)lb_rd32(f->data + 4);
    return true;
}
static inline bool lb_dec_output(const lb_can_frame *f, uint8_t *mode)
{
    if (f->dlc != 1 || f->data[0] > LB_OUT_MODE_MAX) return false;
    *mode = f->data[0]; return true;
}
static inline bool lb_dec_limits(const lb_can_frame *f, lb_limits *m)
{
    if (f->dlc != 8) return false;
    m->p_max_mw = (int32_t)lb_rd32(f->data);
    m->t_derate_dC = (int16_t)lb_rd16(f->data + 4);
    m->policy = f->data[6];
    return m->policy <= LB_POLICY_HOLD;
}
static inline bool lb_dec_cal_write(const lb_can_frame *f, lb_cal_write *m)
{
    if (f->dlc != 6) return false;
    m->item = f->data[0]; m->point = f->data[1]; m->value = (int32_t)lb_rd32(f->data + 2);
    return m->item <= LB_CAL_IMEAS && m->point <= LB_CAL_GAIN;
}
static inline bool lb_dec_reset(const lb_can_frame *f, uint8_t *magic)
{
    if (f->dlc != 1) return false;
    *magic = f->data[0]; return true;
}
static inline bool lb_dec_global_state(const lb_can_frame *f, lb_global_state *m)
{
    if (f->dlc != 4) return false;
    m->budget_w = lb_rd16(f->data); m->flags = f->data[2]; m->seq = f->data[3];
    return true;
}
static inline bool lb_dec_telem_vi(const lb_can_frame *f, lb_set_vi *m) { return lb_dec_set_vi(f, m); }
static inline bool lb_dec_telem_aux(const lb_can_frame *f, lb_telem_aux *m)
{
    if (f->dlc != 8) return false;
    m->t_fet_dC = (int16_t)lb_rd16(f->data); m->t_ind_dC = (int16_t)lb_rd16(f->data + 2);
    m->vbus_10mV = lb_rd16(f->data + 4); m->pout_100mW = lb_rd16(f->data + 6);
    return true;
}
static inline bool lb_dec_status(const lb_can_frame *f, lb_status *m)
{
    if (f->dlc != 8) return false;
    m->state = f->data[0]; m->fault = f->data[1]; m->warn = f->data[2]; m->mode = f->data[3];
    m->vset_echo_10mV = (int16_t)lb_rd16(f->data + 4);
    m->iset_echo_10mA = (int16_t)lb_rd16(f->data + 6);
    return true;
}
static inline bool lb_dec_energy(const lb_can_frame *f, lb_energy *m)
{
    if (f->dlc != 8) return false;
    m->charge_10uAh = (int32_t)lb_rd32(f->data); m->energy_10uWh = (int32_t)lb_rd32(f->data + 4);
    return true;
}
static inline bool lb_dec_fault(const lb_can_frame *f, lb_fault_msg *m)
{
    if (f->dlc != 4) return false;
    m->fault = f->data[0]; m->warn = f->data[1]; m->state = f->data[2];
    return true;
}
static inline bool lb_dec_hello(const lb_can_frame *f, lb_hello *m)
{
    if (f->dlc != 8) return false;
    m->proto_ver = f->data[0]; m->fw_major = f->data[1]; m->fw_minor = f->data[2];
    m->uid = lb_rd32(f->data + 4);
    return true;
}

#endif /* LABBENCH_CAN_H */
