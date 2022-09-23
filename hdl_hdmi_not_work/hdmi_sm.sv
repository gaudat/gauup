module hdmi_sm #(
    // Defaults to 640x480 which should be supported by almost if not all HDMI sinks.
    // See README.md or CEA-861-D for enumeration of video id codes.
    // Pixel repetition, interlaced scans and other special output modes are not implemented (yet).
    parameter int VIDEO_ID_CODE = 1,

    // The IT content bit indicates that image samples are generated in an ad-hoc
    // manner (e.g. directly from values in a framebuffer, as by a PC video
    // card) and therefore aren't suitable for filtering or analog
    // reconstruction.  This is probably what you want if you treat pixels
    // as "squares".  If you generate a properly bandlimited signal or obtain
    // one from elsewhere (e.g. a camera), this can be turned off.
    //
    // This flag also tends to cause receivers to treat RGB values as full
    // range (0-255).
    parameter bit IT_CONTENT = 1'b1,

    // **All parameters below matter ONLY IF you plan on sending auxiliary data (DVI_OUTPUT == 1'b0)**

    // Specify the refresh rate in Hz you are using for audio calculations
    parameter real VIDEO_REFRESH_RATE = 59.94,

    // As specified in Section 7.3, the minimal audio requirements are met: 16-bit or more L-PCM audio at 32 kHz, 44.1 kHz, or 48 kHz.
    // See Table 7-4 or README.md for an enumeration of sampling frequencies supported by HDMI.
    // Note that sinks may not support rates above 48 kHz.
    parameter int AUDIO_RATE = 48000,

    // Defaults to 16-bit audio, the minmimum supported by HDMI sinks. Can be anywhere from 16-bit to 24-bit.
    parameter int AUDIO_BIT_WIDTH = 16,

    // Some HDMI sinks will show the source product description below to users (i.e. in a list of inputs instead of HDMI 1, HDMI 2, etc.).
    // If you care about this, change it below.
    parameter bit [8*8-1:0] VENDOR_NAME = {"Unknown", 8'd0}, // Must be 8 bytes null-padded 7-bit ASCII
    parameter bit [8*16-1:0] PRODUCT_DESCRIPTION = {"FPGA", 96'd0}, // Must be 16 bytes null-padded 7-bit ASCII
    parameter bit [7:0] SOURCE_DEVICE_INFORMATION = 8'h00 // See README.md or CTA-861-G for the list of valid codes
) (
    input [15:0] cx,
    input [15:0] cy,
    input [15:0] screen_width,
    input [15:0] screen_height,
    input [15:0] frame_width,
    input [15:0] frame_height,
    input clk_pixel,
    input clk_audio,
    input reset,
    input [23:0] rgb,
    input hsync,
    input vsync,
    input logic [AUDIO_BIT_WIDTH-1:0] audio_sample_word [1:0],
    input [2:0] i_last_pp,
    output [2:0] o_mode,
    output [29:0] tmds
    );

    // See Section 5.2
    logic video_data_period = 0;
    always_ff @(posedge clk_pixel)
    begin
        if (reset)
            video_data_period <= 0;
        else
            video_data_period <= cx < screen_width && cy < screen_height;
    end

    (* mark_debug = "true" *) logic [2:0] mode = 3'd1;
    assign o_mode = mode;
    
    logic [23:0] video_data = 24'd0;
    logic [5:0] control_data = 6'd0;
    logic [11:0] data_island_data = 12'd0;

    // True hdmi output
    logic video_guard = 1;
    logic video_preamble = 0;
    always_ff @(posedge clk_pixel)
    begin
        if (reset)
            begin
                video_guard <= 1;
                video_preamble <= 0;
            end
        else
            begin
                video_guard <= cx >= frame_width - 2 && cx < frame_width && (cy == frame_height - 1 || cy < screen_height);
                video_preamble <= cx >= frame_width - 10 && cx < frame_width - 2 && (cy == frame_height - 1 || cy < screen_height);
            end
    end

    // See Section 5.2.3.1
    int max_num_packets_alongside;
    logic [4:0] num_packets_alongside;
    always_comb
    begin
        max_num_packets_alongside = ((frame_width - screen_width) /* VD period */ - 2 /* V guard */ - 8 /* V preamble */ - 12 /* 12px control period */ - 2 /* DI guard */ - 2 /* DI start guard */ - 8 /* DI premable */) / 32;
        if (max_num_packets_alongside > 18)
            num_packets_alongside = 5'd18;
        else
            num_packets_alongside = 5'(max_num_packets_alongside);
    end

    logic data_island_period_instantaneous;
    assign data_island_period_instantaneous = num_packets_alongside > 0 && cx >= screen_width + 10 && cx < screen_width + 10 + num_packets_alongside * 32;
    logic packet_enable;
    assign packet_enable = data_island_period_instantaneous && 5'(cx + screen_width + 22) == 5'd0;

    logic data_island_guard = 0;
    logic data_island_preamble = 0;
    logic data_island_period = 0;
    always_ff @(posedge clk_pixel)
    begin
        if (reset)
            begin
                data_island_guard <= 0;
                data_island_preamble <= 0;
                data_island_period <= 0;
            end
        else
            begin
                data_island_guard <= num_packets_alongside > 0 && ((cx >= screen_width + 8 && cx < screen_width + 10) || (cx >= screen_width + 10 + num_packets_alongside * 32 && cx < screen_width + 10 + num_packets_alongside * 32 + 2));
                data_island_preamble <= num_packets_alongside > 0 && cx >= screen_width && cx < screen_width + 8;
                data_island_period <= data_island_period_instantaneous;
            end
    end

        // See Section 5.2.3.4
        (* mark_debug = "true" *) logic [23:0] header;
        logic [55:0] sub [3:0];
        logic video_field_end;
        assign video_field_end = cx == screen_width - 1'b1 && cy == screen_height - 1'b1;
        logic [4:0] packet_pixel_counter;
        packet_picker #(
            .VIDEO_ID_CODE(VIDEO_ID_CODE),
            .IT_CONTENT(IT_CONTENT),
            .AUDIO_RATE(AUDIO_RATE),
            .AUDIO_BIT_WIDTH(AUDIO_BIT_WIDTH),
            .VENDOR_NAME(VENDOR_NAME),
            .PRODUCT_DESCRIPTION(PRODUCT_DESCRIPTION),
            .SOURCE_DEVICE_INFORMATION(SOURCE_DEVICE_INFORMATION)
        ) packet_picker (.clk_pixel(clk_pixel), .clk_audio(clk_audio), .reset(reset), .video_field_end(video_field_end), .packet_enable(packet_enable), .packet_pixel_counter(packet_pixel_counter), .audio_sample_word(audio_sample_word), .header(header), .sub(sub), 
    .acr_N(6144), .acr_CTS(74250), .acr_send_interval(74250), .acr_update(reset), .last_packing_phase(i_last_pp), .gcp_cd_field(4'b0101));
        logic [8:0] packet_data;
        packet_assembler packet_assembler (.clk_pixel(clk_pixel), .reset(reset), .data_island_period(data_island_period), .header(header), .sub(sub), .packet_data(packet_data), .counter(packet_pixel_counter));


    always_ff @(posedge clk_pixel)
    begin
        if (reset)
            begin
                mode <= 3'd2;
                video_data <= 24'd0;
                control_data = 6'd0;
                data_island_data <= 12'd0;
            end
        else
            begin
                mode <= data_island_guard ? 3'd4 : data_island_period ? 3'd3 : video_guard ? 3'd2 : video_data_period ? 3'd1 : 3'd0;
                video_data <= rgb;
                control_data <= {{1'b0, data_island_preamble}, {1'b0, video_preamble || data_island_preamble}, {vsync, hsync}}; // ctrl3, ctrl2, ctrl1, ctrl0, vsync, hsync
                data_island_data[11:4] <= packet_data[8:1];
                data_island_data[3] <= cx != 0;
                data_island_data[2] <= packet_data[0];
                data_island_data[1:0] <= {vsync, hsync};
            end
    end
    
// All logic below relates to the production and output of the 10-bit TMDS code.
logic [9:0] tmds_internal [2:0] /* verilator public_flat */ ;
genvar i;
generate
    // TMDS code production.
    for (i = 0; i < 3; i++)
    begin: tmds_gen
        tmds_channel #(.CN(i)) tmds_channel (.clk_pixel(clk_pixel), .video_data(video_data[i*8+7:i*8]), .data_island_data(data_island_data[i*4+3:i*4]), .control_data(control_data[i*2+1:i*2]), .mode(mode), .tmds(tmds_internal[i]));
        assign tmds[(i+1)*10-1:i*10] = tmds_internal[i];
    end
endgenerate

endmodule
