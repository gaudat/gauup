`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 27.09.2022 21:14:09
// Design Name: 
// Module Name: tenbit_tb
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

module coord_gen
(
    input clk,
    input reset,
    // From tg
    input hsync_in,
    input vsync_in,
    input de_in,
    input valid_in,
    // From pg
    input shiftin,
    output reg[15:0] cx,
    output reg[15:0] cy);


    reg hsync_in_prev;
    always @(posedge clk)
    if (reset) hsync_in_prev <= 0; else hsync_in_prev <= hsync_in;

    reg de_in_set;
    always @(posedge clk)
    if (reset | hsync_in) de_in_set <= 0; else if (de_in) de_in_set <= 1;

    always @(posedge clk) begin
        if (reset | vsync_in) begin
            cx <= 0;
            cy <= 0;
        end else if (de_in_set & hsync_in & ~hsync_in_prev & valid_in) begin
            cx <= 0;
            cy <= cy + 1;
        end else if (de_in & valid_in & shiftin) begin
            cx <= cx + 1;
        end
    end

endmodule

module coord_mod
(
    input [15:0] cx_in,
    input [15:0] cy_in,
    input [15:0] screen_width,
    input [15:0] screen_height,
    output [15:0] cx_out,
    output [15:0] cy_out);

    wire carry;
    assign carry = cx_in >= screen_width;
    assign cx_out = carry ? 0 : cx_in;
    wire carry_y;
    assign carry_y = (carry & cy_in == screen_height - 1) | cy_in >= screen_height;
    assign cy_out = carry_y ? 0 : carry ? cy_in + 1 : cy_in;

endmodule

module tenbit_phase_gen(
    input clk,
    input reset,
    input ready,
    input data_enable,
    input [9:0] pixel_in,
    input hsync_in,
    input vsync_in,
    (* mark_debug = "true" *) output reg packed_p,
    (* mark_debug = "true" *) output reg packed_c,
    (* mark_debug = "true" *) output reg[2:0] packed_phase,
    (* mark_debug = "true" *) output reg[7:0] frag_out,
    (* mark_debug = "true" *) output reg hsync_out,
    (* mark_debug = "true" *) output reg vsync_out,
    (* mark_debug = "true" *) output reg valid,
    (* mark_debug = "true" *) output reg shiftin,
    (* mark_debug = "true" *) output reg de_out,
    output reg[2:0] last_pp
);

    reg[2:0] next_phase;

    reg[9:0] pixel_buf;
    reg hsync_buf, vsync_buf;

    always @(posedge clk) begin
        if (reset) begin
            // Go to 10P0
            packed_p <= 1;
            packed_c <= 0;
            packed_phase <= 3'b000;
            frag_out <= 8'h00;
            hsync_out <= 0;
            vsync_out <= 0;
            valid <= 0;
            shiftin <= 1;
            de_out <= 0;
            last_pp <= 3'b000; // For GCP

            next_phase <= 3'b000;
            pixel_buf <= 10'h000;
            hsync_buf <= 0;
            vsync_buf <= 0;

        end else begin
            valid <= ready;
            de_out <= data_enable;
            if (data_enable) last_pp <= next_phase;
            if (ready) begin // Valid must not depend on ready so kick start it
                if (shiftin) begin
                    pixel_buf <= pixel_in;
                    hsync_buf <= hsync_in;
                    vsync_buf <= vsync_in;
                end
                shiftin <= next_phase == 3'b011 ? 0 : 1;
                packed_phase <= next_phase;
                next_phase <= next_phase == 4 ? 0 : next_phase + 1;
                if (data_enable) begin
                    // DE = 1
                    // Always jump to 10Pn+1
                    packed_p <= 1;
                    packed_c <= 0;
                    // 10Px output
                    hsync_out <= 0;
                    vsync_out <= 0;
                    case (next_phase)
                        3'b000 : frag_out <= pixel_in[7:0];
                        3'b001 : frag_out <= {pixel_in[5:0], pixel_buf[9:8]};
                        3'b010 : frag_out <= {pixel_in[3:0], pixel_buf[9:6]};
                        3'b011 : frag_out <= {pixel_in[1:0], pixel_buf[9:4]};
                        3'b100 : frag_out <= pixel_buf[9:2];
                        default : frag_out <= 8'hxx;
                    endcase
                end else begin
                    // DE = 0
                    casez ({packed_p, packed_c, next_phase})
                        5'b11000 : // 10PC<end> -> 10C0
                        begin
                            packed_p <= 0;
                            packed_c <= 1;
                            // 10Cx output
                            frag_out <= 'd0;
                            casez(next_phase)
                                3'b0?? : begin hsync_out <= hsync_in; vsync_out <= vsync_in; end
                                3'b100 : begin hsync_out <= hsync_buf; vsync_out <= vsync_buf; end
                                default : begin hsync_out <= 'bx; vsync_out <= 'bx; end
                            endcase
                        end
                        5'b11??? : // 10PCn -> 10PCn+1
                        begin
                            packed_p <= 1;
                            packed_c <= 1;
                            // <A> <B> B C D
                            // 10PC2 -> no shift
                            // 10PCx output
                            frag_out <= 'd0;
                            hsync_out <= hsync_buf;
                            vsync_out <= vsync_buf;
                        end
                        5'b01??? : // 10Cn -> 10Cn+1
                        begin
                            packed_p <= 0;
                            packed_c <= 1;
                            // 10Cx output
                            frag_out <= 'd0;
                            casez(next_phase)
                                3'b0?? : begin hsync_out <= hsync_in; vsync_out <= vsync_in; end
                                3'b100 : begin hsync_out <= hsync_buf; vsync_out <= vsync_buf; end
                                default : begin hsync_out <= 'bx; vsync_out <= 'bx; end
                            endcase
                        end
                        5'b1000? : // 10P<0,1> -> 10C<1,2>
                        begin
                            packed_p <= 0;
                            packed_c <= 1;
                            // 10Cx output
                            frag_out <= 'd0;
                            casez(next_phase)
                                3'b0?? : begin hsync_out <= hsync_in; vsync_out <= vsync_in; end
                                3'b100 : begin hsync_out <= hsync_buf; vsync_out <= vsync_buf; end
                                default : begin hsync_out <= 'bx; vsync_out <= 'bx; end
                            endcase
                        end
                        5'b10??? : // 10P<2+> -> 10PC<3+>
                        begin
                            packed_p <= 1;
                            packed_c <= 1; // 10PC2 -> no shift
                            // 10PCx output
                            frag_out <= 'd0;
                            hsync_out <= hsync_buf;
                            vsync_out <= vsync_buf;
                        end
                        default :
                        begin
                            packed_p <= 'bx;
                            packed_c <= 'bx;

                            // 10PCx output
                            frag_out <= 'hxx;
                            hsync_out <= 'bx;
                            vsync_out <= 'bx;
                        end
                    endcase
                end
            end
        end
    end
endmodule

module tenbit_sync_gen #(
    integer screen_width_fp = 640,
    integer frame_width_fp = 660,
    integer hsync_start_fp = 5,
    integer hsync_size_fp = 5,
    integer screen_height = 64,
    integer frame_height = 67,
    integer vsync_start = 1,
    integer vsync_size = 1
)
    (input [15:0] frag_cx,
    input [15:0] frag_cy,
    input clk,
    input reset,
    input ready,
    output reg data_enable,
    output reg hsync,
    output reg vsync,
    output reg sof,
    output reg[15:0] o_frag_cx,
    output reg[15:0] o_frag_cy,
    output reg valid
);

    always @(posedge clk) begin

        if (reset) valid <= 0; else begin

            valid <= ready;

            data_enable <= frag_cx < screen_width_fp & frag_cy < screen_height;
            hsync <= frag_cx >= screen_width_fp + hsync_start_fp & frag_cx < screen_width_fp + hsync_start_fp + hsync_size_fp;

            // vsync synchronous to hsync rising edge
            vsync <= (frag_cy == screen_height + vsync_start - 1 & frag_cx >= screen_width_fp + hsync_start_fp) | (
            frag_cy >= screen_height + vsync_start & frag_cy < screen_height + vsync_start + vsync_size - 1) | (
            frag_cy == screen_height + vsync_start + vsync_size - 1 & frag_cx < screen_width_fp + hsync_start_fp);

            sof <= frag_cx == 0 & frag_cy == 0;
            o_frag_cx <= frag_cx;
            o_frag_cy <= frag_cy;
        end
    end

endmodule

module tenbit_timing_gen #(
    // 1280 1650 110 40 
    // 720 750 5 5
    integer screen_width_fp = 6400, // Number of fragments: 1280 x 1.25 x 4
    integer frame_width_fp = 8250,
    integer hsync_start_fp = 550,
    integer hsync_size_fp = 200,
    integer screen_height = 720,
    integer frame_height = 750,
    integer vsync_start = 5,
    integer vsync_size = 5
    //128 132 1 1
    // 64 67 1 1
    //integer screen_width_fp = 640,
    //integer frame_width_fp = 660,
    //integer hsync_start_fp = 5,
    //integer hsync_size_fp = 5,
    //integer screen_height = 64,
    //integer frame_height = 67,
    //integer vsync_start = 1,
    //integer vsync_size = 1
)
    (input clk,
    input reset,
    output reg[15:0] o_frag_cx,
    output reg[15:0] o_frag_cy,
    output reg[15:0] o_screen_width,
    output reg[15:0] o_frame_width,
    output reg valid,
    output reg data_enable,
    output reg hsync,
    output reg vsync,
    output reg sof
);

    reg cg_valid;
    reg pg_de;

    reg[15:0] frag_counter;
    reg[15:0] frag_limit; // incr 1, loaded at start of line
    reg[15:0] line_counter;
    reg[15:0] frag_cx, frag_cy;
    reg[1:0] frac_phase; // 0 -> 0 0 0 0, 1 -> 1 0 0 0
    reg[15:0] next_screen_width;
    reg[15:0] next_frame_width;

    always @(posedge clk) begin
        if (reset) begin
            frag_counter <= 0;
            line_counter <= 0;
            frag_cx <= 0;
            frag_cy <= 0;
            pg_de <= 1;
            cg_valid <= 0;
            frac_phase <= 1;
            next_screen_width <= screen_width_fp[17:2] + (screen_width_fp % 4 ? 1 : 0);
            o_screen_width <= screen_width_fp[17:2] + (screen_width_fp % 4 ? 1 : 0);
            frag_limit <= frame_width_fp[17:2] + (frame_width_fp % 4 ? 1 : 0);
            next_frame_width <= frame_width_fp[17:2] + (frame_width_fp % 4 ? 1 : 0);
            o_frame_width <= frame_width_fp[17:2] + (frame_width_fp % 4 ? 1 : 0);
        end else begin
            cg_valid <= 1;

            if (frag_counter + 1 >= frag_limit) begin
                // Reset counter 
                frag_counter <= 0;
                if (line_counter >= frame_height - 1)
                    line_counter <= 0;
                else
                    line_counter <= line_counter + 1;
                    // Update limit
                frac_phase <= (frac_phase + 1) % 4;
                if (frame_width_fp[1:0] > frac_phase) begin
                    frag_limit <= frame_width_fp[17:2] + 1;
                    next_frame_width <= frame_width_fp[17:2] + 1;
                end else begin
                    frag_limit <= frame_width_fp[17:2];
                    next_frame_width <= frame_width_fp[17:2];
                end
                if (screen_width_fp[1:0] > frac_phase)
                    next_screen_width <= screen_width_fp[17:2] + 1;
                else
                    next_screen_width <= screen_width_fp[17:2];
            end else begin
                frag_counter <= frag_counter + 1;
            end

            frag_cx <= frag_counter << 2;
            frag_cy <= line_counter;
            if (frag_counter == 1) begin
                o_frame_width <= next_frame_width;
                o_screen_width <= next_screen_width;
            end
        end
    end


    always @(posedge clk) begin

        if (reset) begin
            valid <= 0;
            data_enable <= 0;
            hsync <= 0;
            vsync <= 0;
            sof <= 0;
            o_frag_cx <= 0;
            o_frag_cy <= 0;
        end else begin

            valid <= cg_valid;

            data_enable <= frag_cx < screen_width_fp & frag_cy < screen_height;
            hsync <= frag_cx >= screen_width_fp + hsync_start_fp & frag_cx < screen_width_fp + hsync_start_fp + hsync_size_fp;

            // vsync synchronous to hsync rising edge
            vsync <= (frag_cy == screen_height + vsync_start - 1 & frag_cx >= screen_width_fp + hsync_start_fp) | (
            frag_cy >= screen_height + vsync_start & frag_cy < screen_height + vsync_start + vsync_size - 1) | (
            frag_cy == screen_height + vsync_start + vsync_size - 1 & frag_cx < screen_width_fp + hsync_start_fp);

            sof <= frag_cx == 0 & frag_cy == 0;
            o_frag_cx <= frag_cx;
            o_frag_cy <= frag_cy;
        end
    end

endmodule

module tenbit_newest_pixel(
    input clk,
    input reset,
    input shiftin,
    input hsync_in,
    input vsync_in,
    input de_in,
    output reg[9:0] newest_pixel);

    reg[15:0] cx;
    reg[15:0] cy;

    always @(posedge clk) begin
        if (reset) // On reset give first pixel
            begin
                newest_pixel <= 'h111;
            end
        else if (de_in & shiftin) begin
            newest_pixel <= newest_pixel + 'h111;
        end
    end


    reg hsync_in_prev;
    always @(posedge clk)
    if (reset) hsync_in_prev <= 0; else hsync_in_prev <= hsync_in;

    reg de_in_set;
    always @(posedge clk)
    if (reset | hsync_in) de_in_set <= 0; else if (de_in) de_in_set <= 1;

    always @(posedge clk) begin
        if (reset | vsync_in) begin
            cx <= 0;
            cy <= 0;
        end else if (de_in_set & hsync_in & ~hsync_in_prev) begin
            cx <= 0;
            cy <= cy + 1;
        end else if (de_in & shiftin) begin
            cx <= cx + 1;
        end
    end

endmodule

module tenbit_ramp_gen(
    input clk,
    input reset,
    input shiftin,
    input hsync_in,
    input vsync_in,
    input de_in,
    output reg[9:0] pixel);

    (* mark_debug = "true" *) reg[15:0] cx;
    (* mark_debug = "true" *) reg[15:0] cy;

    always @(posedge clk) begin
        if (reset) // On reset give first pixel
            begin
                pixel <= 'h000;
            end
        else if (de_in & shiftin) begin
            pixel <= cx[9:0];
        end
    end


    reg hsync_in_prev;
    always @(posedge clk)
    if (reset) hsync_in_prev <= 0; else hsync_in_prev <= hsync_in;

    reg de_in_set;
    always @(posedge clk)
    if (reset | hsync_in) de_in_set <= 0; else if (de_in) de_in_set <= 1;

    always @(posedge clk) begin
        if (reset | vsync_in) begin
            cx <= 0;
            cy <= 0;
        end else if (de_in_set & hsync_in & ~hsync_in_prev) begin
            cx <= 0;
            cy <= cy + 1;
        end else if (de_in & shiftin) begin
            cx <= cx + 1;
        end
    end

endmodule
    
    