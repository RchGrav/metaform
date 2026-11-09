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

2. Deleting the Relation (Orphaning):
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

1. The Command to Scan for Orphans


{
  "orphaned": {}
}


2. The Engine Response

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

3. Removing a Specific Property Value:
```
{
  "update": {
    "code.masher.widget": {
      "role": null
    }
  }
}
```
4. Query, enter the object
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
