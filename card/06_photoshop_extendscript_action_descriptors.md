# Wiki 06: Photoshop ExtendScript & ActionDescriptor Reference

When controlling Adobe Photoshop programmatically via scripts or MCP (`photoshop-mcp`), Photoshop's standard DOM scripting does not natively cover advanced channel and mask creation. We use **ActionDescriptors** (Photoshop Action Manager) via `executeAction` for precise control.

---

## 1. Creating an Attached Layer Mask from a Selection or Channel

To attach a **Layer Mask** directly to the active layer thumbnail:

```javascript
#target photoshop

/**
 * Creates a Layer Mask attached to the active layer from a spot channel or selection
 * @param {string} channelName Name of the Spot Channel to load as selection
 */
function createLayerMaskFromChannel(channelName) {
    var s2t = stringIDToTypeID;

    // 1. Load the spot channel as an active selection (Ctrl + Click)
    var descSet = new ActionDescriptor();
    var refSet = new ActionReference();
    var refChannel = new ActionReference();
    
    refSet.putProperty(s2t("channel"), s2t("selection"));
    descSet.putReference(s2t("null"), refSet);
    
    refChannel.putName(s2t("channel"), channelName);
    descSet.putReference(s2t("to"), refChannel);
    
    executeAction(s2t("set"), descSet, DialogModes.NO);

    // 2. Create attached Layer Mask from selection (Reveal Selection)
    var descMake = new ActionDescriptor();
    var refMake = new ActionReference();
    
    refMake.putEnumerated(s2t("channel"), s2t("channel"), s2t("mask"));
    descMake.putReference(s2t("at"), refMake);
    descMake.putEnumerated(s2t("using"), s2t("userMaskEnabled"), s2t("revealSelection"));
    
    executeAction(s2t("make"), descMake, DialogModes.NO);
}
```

---

## 2. Creating a Spot Channel for UV Printing

To create a **New Spot Channel** named `White`, `Varnish`, or `Foil`:

```javascript
function createSpotChannel(name, red, green, blue, solidity) {
    var s2t = stringIDToTypeID;
    var desc = new ActionDescriptor();
    var ref = new ActionReference();
    
    ref.putClass(s2t("channel"));
    desc.putReference(s2t("null"), ref);
    
    var channelDesc = new ActionDescriptor();
    channelDesc.putString(s2t("name"), name);
    channelDesc.putEnumerated(s2t("channelType"), s2t("channelType"), s2t("spot"));
    
    // Set Spot Channel Overlay Color
    var colorDesc = new ActionDescriptor();
    colorDesc.putDouble(s2t("red"), red);
    colorDesc.putDouble(s2t("green"), green);
    colorDesc.putDouble(s2t("blue"), blue);
    channelDesc.putObject(s2t("color"), s2t("RGBColor"), colorDesc);
    
    channelDesc.putInteger(s2t("opacity"), solidity); // Solidity 0-100%
    desc.putObject(s2t("using"), s2t("channel"), channelDesc);
    
    executeAction(s2t("make"), desc, DialogModes.NO);
}

// Usage Example: Create White Ink Spot Channel (Solidity 100%)
// createSpotChannel("White", 255, 0, 0, 100);
```

---

## 3. High-Frequency `photoshop-mcp` Tool Reference

| MCP Tool Name | Description | Key Arguments |
|---|---|---|
| `photoshop_get_state` | Returns document dimensions, layer stack, active layer, and selection bounds | None |
| `photoshop_get_preview` | Returns base64 JPEG thumbnail of the canvas for visual AI verification | `max_width` |
| `photoshop_duplicate_layer` | Duplicates active layer | None |
| `photoshop_rename_layer` | Renames active layer | `name` |
| `photoshop_create_layer_mask` | Creates layer mask on active layer from selection | None |
| `photoshop_select_subject` | Runs Sensei AI subject selection | None |
| `photoshop_execute_script` | Runs custom ExtendScript JSX code inside Photoshop | `script` |
