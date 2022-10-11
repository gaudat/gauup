// Implementation of HDMI General Control packet.

// See Section 8.2.1
module general_control_packet
(
    input logic set_avmute,
    input logic clear_avmute,
    input logic[2:0] pixel_packing_phase,
    input logic[3:0] cd_field,
    input logic default_phase,
    output logic [23:0] header,
    output logic [55:0] sub [3:0]
);

typedef enum {PP_PHASE_4 = 0, PP_PHASE_1, PP_PHASE_2, PP_PHASE_3} pixel_packing_phase_t;
typedef enum {CD_NOT_INDICATED = 0, CD_24_BITS_PER_PIXEL = 4, CD_30_BITS_PER_PIXEL, CD_36_BITS_PER_PIXEL, CD_48_BITS_PER_PIXEL} color_depth_t;

(* mark_debug = "true" *) logic [7:0] general_control_subpacket[6:0];

assign header = 24'b00000011_00000000_00000000;

logic[3:0] pp_field;

assign pp_field = pixel_packing_phase == 4 ? 4'b0000 : 
    pixel_packing_phase == 1 ? 4'b0001 : 
    pixel_packing_phase == 2 ? 4'b0010 : 
    pixel_packing_phase == 3 ? 4'b0011 : 
    4'bxxxx;

assign general_control_subpacket[0] = {3'b0, clear_avmute, 3'b0, set_avmute};
assign general_control_subpacket[1] = {pp_field, cd_field};
assign general_control_subpacket[2] = {7'b0, default_phase};
assign general_control_subpacket[3] = 8'b0;
assign general_control_subpacket[4] = 8'b0;
assign general_control_subpacket[5] = 8'b0;
assign general_control_subpacket[6] = 8'b0;

genvar sub_i, sub_byte_i;
generate
for (sub_i = 0; sub_i < 4; sub_i++) begin
for (sub_byte_i = 0; sub_byte_i < 7; sub_byte_i++) begin
assign sub[sub_i][(sub_byte_i+1)*8-1:sub_byte_i*8] = general_control_subpacket[sub_byte_i];
end
end
endgenerate

endmodule
