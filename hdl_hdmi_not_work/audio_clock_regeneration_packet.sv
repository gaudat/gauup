// Implementation of HDMI audio clock regeneration packet
// By Sameer Puri https://github.com/sameer

// See HDMI 1.4b Section 5.3.3
module audio_clock_regeneration_packet
(
    input logic [19:0] in_N = 0,
    input logic [19:0] in_CTS = 0,
    input logic [19:0] in_send_interval = 0, // Number of TMDS clocks between ACR packets
    input logic update,
    input logic clk_pixel, // TMDS clock is clk_pixel
    input logic clk_audio, // 1 * audio sample rate [fs]. Should be 128* according to spec
    output logic clk_audio_counter_wrap = 0,
    output logic [23:0] header,
    output logic [55:0] sub [3:0]
);

// "An HDMI Sink shall ignore bytes HB1 and HB2 of the Audio Clock Regeneration Packet header."
`ifdef MODEL_TECH
assign header = {8'd0, 8'd0, 8'd1};
`else
assign header = {8'dX, 8'dX, 8'd1};
`endif

logic [19:0] N, cycle_time_stamp, send_interval;

// Toggle clk_audio_counter_wrap if a new packet needs to be sent
always_ff @(posedge clk_pixel) begin
    if (update) begin
        N <= in_N;
        cycle_time_stamp <= in_CTS;
        send_interval <= in_send_interval;
    end
end

// Ideally ACR packet is sent at 1 KHz by observing pattern in preferred N values.
// Worst case: 600 MHz at 1 KHz = 6e5 counts. 20 bits should be enough
logic [19:0] acr_packet_counter;

// This packet should be sent every 128 * fs / N clocks
always_ff @(posedge clk_pixel) begin
    if (N > 0 && cycle_time_stamp > 0 && send_interval > 0) begin
        if (acr_packet_counter >= send_interval) begin
            clk_audio_counter_wrap = ~clk_audio_counter_wrap;
            acr_packet_counter <= 0;
        end
        else
            acr_packet_counter <= acr_packet_counter + 1;
        
    end
end

// "The four Subpackets each contain the same Audio Clock regeneration Subpacket."
genvar i;
generate
    for (i = 0; i < 4; i++)
    begin: same_packet
        assign sub[i] = {N[7:0], N[15:8], {4'd0, N[19:16]}, cycle_time_stamp[7:0], cycle_time_stamp[15:8], {4'd0, cycle_time_stamp[19:16]}, 8'd0};
    end
endgenerate

endmodule
