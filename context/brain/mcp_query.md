The Initial State / Configuration:
```
{
  "mashtrac": {
    "id": "carverj-mashtrac-2026-10-31",
    "name": "Mashtrac Protocol",
    "project": "carverj/mashtrac",
    "code": {
      "masher": {
        "widget": {
          "name": "mashbox",
          "role": "SE",
          "uri": "./src/widgets/mashbox.c"
        }
      },
      "protocol": {
        "network": {
          "tracker": {
            "cs": {
              "name_length": 4
              "name": "mashtrac",
              "role": "DE",
              "uri": "./src/network/mashtrac.c",
              "wants": [
                {
                  "code.masher.widget": {
                    "goal": "Receive the mash data to relay it.",
                    "function": "Prepared mash data packets.",
                    "intent": "receive"
                  }
                }
              ]
            }
          }
        }
      }
    }
  }
}

```
{
  "delete": {
    "code.masher.widget": {}
  }
}
```


```
{
  "delete": {
    "code.masher.widget": {}
  },
  "status": "error",
  "message": "cannot delete, 'code.masher.widget', must be orphaned first",
  "remediation": {
    "delete": {
      "code.protocol.network.tracker.cs": {
        "wants": [
          "code.masher.widget"
        ]
      }
    }
  }
}
```

Deleting the Relation (Orphaning):
```
{
  "delete": {
    "code.protocol.network.tracker.cs": {
      "wants": [
        "code.masher.widget"
      ]
    }
  }
}
```

The Command to Scan for Orphans


{
  "orphaned": {}
}


The Engine Response

The engine executes the scan and returns the unreferenced paths under that same root operation key:
json
{
  "orphaned": {
    "code.masher.widget": {
      "name_length": 3,
      "name": "mashbox",
      "role": "SE",
      "uri": "./src/widgets/mashbox.c"
    }
  }
}

Removing a Specific Property Value:
```
{
  "update": {
    "code.masher.widget": {
      "role": null
    }
  }
}
```
Query, similar to orphaned, orphaned resolves as elements who are not attached.
```
{
"code.masher.widget": {}
}
```
```
{
  "code.masher.widget": {
    "name_length": 3,
    "name": "mashbox",
    "uri": "./src/widgets/mashbox.c"
  }
}

6. Deleting the Orphaned Object:
```
{
  "delete": {
    "code.masher.widget": {}
  }
}
```


name is like a internal or alternate alias name that doesnt match the name used in the namespace address, the address name is what it is while the name is the term used to refer to it
