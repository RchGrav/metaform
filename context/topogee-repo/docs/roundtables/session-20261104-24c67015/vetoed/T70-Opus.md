Proposal for bounded device scheduling, which would settle the T55 dispute:
- The device has two lanes.
- The inhibit lane holds one slot. The newest inhibit replaces the older one. It is never durable, and it preempts the command lane.
- The command lane is a bounded FIFO of depth N. When it is full, the device refuses new commands; it never drops them silently.
- An inhibit clears the command lane and advances the lease generation.
- The limit is that an inhibit takes effect within one control tick.
- The test: measure inhibit latency with a full command lane.
