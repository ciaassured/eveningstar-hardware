# Ordering PCB from JLCPCB

This guide includes instructions on how to order an assembled PCB from [JLCPCB](https://jlcpcb.com)

## Instant Quote

1. The first step is to visit the [JLCPCB quote page](https://cart.jlcpcb.com/quote) or visit the home-page and click **Get Instant Quote**.

2. Sign In. You must sign in later anyway, and if you don't sign in now the form sometimes glitches out and changes options.

3. Select **Add gerber file** and upload [EveningStar.zip](/pcb/production/EveningStar.zip).

4. Select the number of PCBs you want to order.

5. Select desired PCB colour (Be aware that this increases lead-time).

6. Update **Mark on PCB** to **2D barcode (Serial Number)**.

    1. Update **Printing** to **2D barcode & Number**.

    2. Update **Prefix** to **github_ciaassured**.

    3. Update **2D Barcode Size** to **10*10mm**.

    4. Update **2D Barcode Position** to **Specify Position**.

7. Enable PCB Assembly.

8. Update **Tooling holes** to **Added by Customer**

9. Select desired lead-time and shipping options on the right-hand side-bar.

10. Review options and compare with this [screenshot](/image/jlcpcb_quote_screenshot.png).

11. Click **Next**.

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

If parts are missing un unavailable, substitutes must be found.

> [!NOTE]
> Extended parts cost much more than Basic parts because there's a loading fee for each extended part. This is not really something to worry about at this stage, but should be considered when updating the board design.

7. Click **NEXT**.

8. The component placement screen should show you a 3D render of the board with the parts populated. Make sure to have a look and check that components things look like they're in the right place, and it's also a good idea to check that the components are rotated correctly by checking the pads on the board match the component pads, and any corner indicators (usually small circle) match on the component and the board.

9. Click **NEXT**.

10. Select something for the product decription. I used **Sensor\Controller\Precision Instrument > Temperature Sensor**.

10. Click **SAVE TO CART**.

11. The rest of the process should be reasonably self explanatory.
