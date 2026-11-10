# cmpe273-module7-time-ordering-coordination

## Run instructions:

```sh
python3 order_simulation.py
```

## Correct event ordering
![alt text](image.png)
Even though v2 is received first, holding until v1 is received before applying v1 then v2 demonstrates correct event ordering

## Duplicate handling
![alt text](image.png)
Duplicate/stale version 2 is ignored after we already have an applied version 2 that was waiting on version 1

## Missing-event case
![alt text](image-1.png)
On missing events 1 and 2, only event 3 is received and missing events are recorded

## Stale-worker rejection
![alt text](image-2.png)
Ignores stale worker A update after the current token is greater than the update token

## Reflection:
Timestamps alone are not enough to guarantee correct event ordering in a distributed system because the times returned can be out of sync due to distributed machines (as are in a distributed system) not having perfectly synced clocks. Because the machines are connect via network, network delays can also cause out of sync timing. Instead of using timestamps which can be inaccurate or delayed, we should use ordering mechanisms such as token numbers as used in this assignment to ensure correct ordering in distributed systems.
