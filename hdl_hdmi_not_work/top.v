`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 02.09.2022 17:45:24
// Design Name: 
// Module Name: top
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////

module top(
    input clk,
    input clk_x5,
    input reset,
    output [2:0] tmds,
    output   tmds_clock
);
    
    (* mark_debug = "true" *) wire [9:0] newest_pixel;

    (* mark_debug = "true" *) wire tg_valid;
    (* mark_debug = "true" *) wire tg_de; 
    (* mark_debug = "true" *) wire tg_hsync; 
    (* mark_debug = "true" *) wire tg_vsync;
    (* mark_debug = "true" *) wire shiftin;
    (* mark_debug = "true" *) wire[15:0] tg_frag_cx;
    (* mark_debug = "true" *) wire[15:0] tg_frag_cy;
    (* mark_debug = "true" *) wire[15:0] tg_screen_width;
    (* mark_debug = "true" *) wire[15:0] tg_frame_width;
    
    tenbit_timing_gen tg(.clk(clk), .reset(reset), .valid(tg_valid), .data_enable(tg_de), .sof(tg_sof), .o_frag_cx(tg_frag_cx), .o_frag_cy(tg_frag_cy), .hsync(tg_hsync), .vsync(tg_vsync), .o_screen_width(tg_screen_width), .o_frame_width(tg_frame_width));

    (* mark_debug = "true" *) wire[7:0] frag_out;
    (* mark_debug = "true" *) wire frag_hsync;
    (* mark_debug = "true" *) wire frag_vsync;
    (* mark_debug = "true" *) wire[2:0] pg_last_pp;
   
    tenbit_phase_gen pg(.clk(clk), .reset(reset), .ready(tg_valid), .data_enable(tg_de), .valid(pg_valid), .shiftin(shiftin), .pixel_in(newest_pixel), .hsync_in(tg_hsync), .vsync_in(tg_vsync), .frag_out(frag_out), .hsync_out(frag_hsync), .vsync_out(frag_vsync), .last_pp(pg_last_pp));

    tenbit_ramp_gen tpg(.clk(clk), .reset(reset), .hsync_in(tg_hsync), .vsync_in(tg_vsync), .de_in(tg_de), .shiftin(shiftin & tg_valid), .pixel(newest_pixel));

    (* mark_debug = "true" *) wire[15:0] xyg_cx;
    (* mark_debug = "true" *) wire[15:0] xyg_cy;

    coord_gen xyg(.clk(clk), .reset(reset), .hsync_in(tg_hsync), .vsync_in(tg_vsync), .de_in(tg_de), .valid_in(tg_valid), .shiftin(shiftin), .cx(xyg_cx), .cy(xyg_cy));

    coord_mod xym(.cx_in(xyg_cx), .cy_in(xyg_cy), .screen_width(1280), .screen_height(720));
    
    wire [29:0] tmds_internal;

    hdmi_sm hs(.cx(tg_frag_cx >> 2), .cy(tg_frag_cy), .screen_width(tg_screen_width), .frame_width(tg_frame_width), .screen_height(720), .frame_height(750), .clk_pixel(clk), .reset(reset), .clk_audio(0), .rgb({3{frag_out}}), .hsync(frag_hsync), .vsync(frag_vsync), .i_last_pp(pg_last_pp), .tmds(tmds_internal));

    serializer ser(.clk_pixel(clk), .clk_pixel_x5(clk_x5), .reset(reset), .tmds_internal(tmds_internal), .tmds(tmds), .tmds_clock(tmds_clock));

endmodule
