# Ordering PCB from JLCPCB

This guide includes instructions on how to order an assembled PCB from [JLCPCB](https://jlcpcb.com)

## Production files

Download the production files from the latest GitHub release:

- [`EveningStar-gerbers.zip`](https://github.com/ciaassured/eveningstar-hardware/releases/latest/download/EveningStar-gerbers.zip)
- [`EveningStar-bom.csv`](https://github.com/ciaassured/eveningstar-hardware/releases/latest/download/EveningStar-bom.csv)
- [`EveningStar-cpl.csv`](https://github.com/ciaassured/eveningstar-hardware/releases/latest/download/EveningStar-cpl.csv)

To order an older hardware version, take the files from that version's release
instead. Releases up to v1.0.1 name them `EveningStar.zip`, `bom.csv`, and
`positions.csv`.

Alternatively, build them from a checkout of the tag being ordered by running
the following command from the repository root:

```sh
nix build .#production
```

This leaves the same files under `result/`. Do not use manufacturing files from
a different tag or an unreviewed working tree.

## Instant Quote

1. The first step is to visit the [JLCPCB quote page](https://cart.jlcpcb.com/quote) or visit the home-page and click **Get Instant Quote**.

2. Sign In. You must sign in later anyway, and if you don't sign in now the form sometimes glitches out and changes options.

3. Select **Add gerber file** and upload `EveningStar-gerbers.zip`.

4. Select the number of PCBs you want to order.

5. Select desired PCB colour (Be aware that this increases lead-time).

6. Update **Mark on PCB** to **2D barcode (Serial Number)**.

   1. Update **Printing** to **Number Only**.

   2. Update **2D Barcode Position** to **Specify Position**.

   3. Click **Submit**.

7. Enable PCB Assembly.

8. Update **Tooling holes** to **Added by Customer**

9. Update **Assembly remark** to **Yes**

   1. Enter the following remark

   ```plain
   Please fit CN1 by plugging it into P1 on every board after soldering.

   CN1 is the plug half of the pluggable terminal block (LCSC C8466, KANGNEX WJ15EDGK-3.81-02P-14-00A) and mates with the soldered header P1 (LCSC C8387, WJ15EDGRC-3.81-2P). CN1 is not soldered, so it is in the BOM but has no entry in the CPL file.

   Please insert it fully.
   ```

10. Select desired lead-time and shipping options on the right-hand side-bar.

11. Review options and compare with this [screenshot](/assets/jlcpcb_quote_screenshot.png).

12. Click **Next**.

## Assembly Parts

At this point you should be looking at a render of the PCB with no parts.


1. Check that both the Top and Bottom sides look good.

> [!NOTE]
> The bottom layer of the PCB appears backwards because the render doesn't flip it. This is fine, it will come out the right way in real life.

2. Click **NEXT**.

3. Click **Add BOM File** and upload `EveningStar-bom.csv`.

4. Click **Add CPL File** and upload `EveningStar-cpl.csv`.

5. Click **Process BOM & CPL**.

> [!NOTE]
> JLCPCB warns about CN1:
>
> ```plain
> The below parts won't be assembled due to data missing.
> CN1 designator don't exist in the CPL file.
> ```
>
> This is expected. CN1 is the plug half of the pluggable terminal block. It
> is not soldered, so it has no placement in the CPL file, and the assembly
> remark asks JLCPCB to plug it into P1 instead.
>
> Ignore the warning and continue.

6. At this point you should see a list of all the parts and how much they cost.
It's important that all parts are selected in the right hand column otherwise they will be missing when you get your board.

If parts are missing un unavailable, substitutes must be found.

> [!NOTE]
> Extended parts cost much more than Basic parts because there's a loading fee for each extended part. This is not really something to worry about at this stage, but should be considered when updating the board design.

7. Click **NEXT**.

8. The component placement screen should show you a 3D render of the board with the parts populated. Make sure to have a look and check that components things look like they're in the right place, and it's also a good idea to check that the components are rotated correctly by checking the pads on the board match the component pads, and any corner indicators (usually small circle) match on the component and the board.

9. Click **NEXT**.

10. Select something for the product decription. I used **Sensor\Controller\Precision Instrument > Temperature Sensor**.

10. Click **SAVE TO CART**.

11. The rest of the process should be reasonably self explanatory.
