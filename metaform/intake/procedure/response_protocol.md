- When the intake is finished, the recorded elements and dependencies express the final annealed shape after Method step 12. Keep the root element list minimal, coarse, and shallow per Goal and Constraints by absorbing subparts. Do not leave absorbed subparts recorded as independent root elements; instead, remove them and preserve their atomic realities exclusively as subtype dependencies inside the load-bearing parent's matching purpose join.
- An element's identity is its namespace_address attribute, not its readable name. "tool registry" is prose; code.registry.tool is the element. Any reference to an element, in a dependency or anywhere else, must use that namespace_address value, never the name alone. A name with no matching namespace_address isn't a valid reference to anything.
- All namespace records are elements. An element inside the AUE carries exactly one role of DE, SE, or NE. A CQU outside the AUE is represented as an element with role CQU; it does not receive a role of DE, SE, or NE. PE is not a role attribute: it is the join's other endpoint. The same element may bear an OP as an RE in one dependency and provide an EF as a PE in another without duplication.
- Joins connect the RE bearing the OP to the PE providing for it, and carry purpose, ef and ifd. This applies to every join.
- prepend upstream and downstream to the namespace address to indicate upstream requirements and downstream users (cqu) or dependants
- Every element carries one uri: the single URI that best represents the element. For code it is the entry point. For a photo it is the path to the photo. One uri is a pointer an agent can follow to see the element for itself; a list of every member is an inventory, and it is out of date tomorrow.
- A folder or collection is surveyed whole: observe every member before any group is named. A group inferred from a sample cannot contain the types the sample missed, and the map would then describe the sample and not the artifact. State in the description how many members were observed.

Schema (json):

```json
{
  "$schema": "https://json-schema.org",
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["pending", "active", "completed"]
    }
  },
  "required": ["status"]
}
```
