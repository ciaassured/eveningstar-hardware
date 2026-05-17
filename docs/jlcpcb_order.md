# Ordering PCB from JLCPCB

This guide includes instructions on how to order an assembled PCB from [JLCPCB](https://jlcpcb.com)

## Instant Quote

1. The first step is to visit the [JLCPCB quote page](https://cart.jlcpcb.com/quote) or visit the home-page and click **Get Instant Quote**.

2. Sign In. You must sign in later anyway, and if you don't sign in now the form sometimes glitches out and changes options.

3. Select **Add gerber file** and upload [EveningStar.zip](/pcb/production/EveningStar.zip).

4. If the board dimensions are missing, enter them as **145.5mm x 43.6mm**.

5. Select the number of PCBs you want to order.

6. Select desired PCB colour (Be aware that this increases lead-time).

7. Update **Mark on PCB** to **2D barcode (Serial Number)**.

    1. Update **Printing** to **2D barcode & Number**.

    2. Update **Prefix** to **github_ciaassured**.

    3. Update **2D Barcode Size** to **10*10mm**.

    4. Update **2D Barcode Position** to **Specify Position**.

8. Enable PCB Assembly.

9. Update **Tooling holes** to **Added by Customer**

10. Select desired lead-time and shipping options on the right-hand side-bar.

11. Review options and compare with this [screenshot](/image/jlcpcb_quote_screenshot.png).

12. Click **Next**.

## Assembly Parts

At this point you should be looking at a render of the PCB with no parts.



1. Check that both the Top and Bottom sides look good.

> [!NOTE]
> The bottom layer of the PCB appears backwards because the render doesn't flip it. This is fine, it will come out the right way in real life.

2. Click **NEXT**.

3. Click **Add BOM File** and upload [bom.csv](/pcb/production/bom.csv).

4. Click **Add CPL File** and upload [positions.csv](/pcb/production/positions.csv).

5. Click **Process BOM & CPL**.

6. At this point you should see a list of all the parts and how much they cost.
It's important that all parts are selected otherwise they will be missing when you get your board.

> [!NOTE]
> Extended parts cost much more than Basic parts because there's a loading fee for each extended part. This is not really something to worry about at this stage, but should be considered when updating the board design.