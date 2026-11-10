"""Demonstrate versioned order events and fencing tokens."""

from dataclasses import dataclass


VALID_STATUSES = {"CREATED", "PAID", "SHIPPED"}


@dataclass(frozen=True)
class OrderEvent:
    order_id: str
    version: int
    status: str

    def __post_init__(self) -> None:
        if not self.order_id:
            raise ValueError("order_id must not be empty")
        if self.version < 1:
            raise ValueError("version must be a positive integer")
        if self.status not in VALID_STATUSES:
            raise ValueError(f"unsupported status: {self.status}")


class OrderProcessor:
    """Apply each order's updates consecutively, buffering version gaps."""

    def __init__(self) -> None:
        self.versions: dict[str, int] = {}
        self.statuses: dict[str, str] = {}
        self.pending: dict[str, dict[int, OrderEvent]] = {}

    def receive(self, event: OrderEvent) -> list[str]:
        order_id = event.order_id
        current_version = self.versions.get(order_id, 0)
        pending_for_order = self.pending.setdefault(order_id, {})

        if event.version <= current_version:
            return [f"IGNORED duplicate/stale version {event.version}"]

        existing = pending_for_order.get(event.version)
        if existing is not None:
            if existing != event:
                raise ValueError(
                    f"conflicting events for {order_id} version {event.version}"
                )
            return [f"IGNORED duplicate pending version {event.version}"]

        pending_for_order[event.version] = event
        expected_version = current_version + 1
        if event.version > expected_version:
            missing_range = (
                str(expected_version)
                if event.version - 1 == expected_version
                else f"{expected_version}-{event.version - 1}"
            )
            return [
                f"PENDING version {event.version}; waiting for version "
                f"{expected_version} (missing versions: "
                f"{missing_range})"
            ]

        messages: list[str] = []
        while self.versions.get(order_id, 0) + 1 in pending_for_order:
            next_version = self.versions.get(order_id, 0) + 1
            next_event = pending_for_order.pop(next_version)
            self.versions[order_id] = next_version
            self.statuses[order_id] = next_event.status
            messages.append(f"APPLIED version {next_version}: {next_event.status}")

        return messages

    def missing_versions(self, order_id: str) -> list[int]:
        """Return missing versions before the highest version currently pending."""
        pending_for_order = self.pending.get(order_id, {})
        if not pending_for_order:
            return []

        first_missing = self.versions.get(order_id, 0) + 1
        highest_pending = max(pending_for_order)
        return [
            version
            for version in range(first_missing, highest_pending)
            if version not in pending_for_order
        ]


class FencedOrderStore:
    """Reject writes from workers holding an older fencing token."""

    def __init__(self) -> None:
        self.highest_tokens: dict[str, int] = {}
        self.statuses: dict[str, str] = {}

    def write(self, order_id: str, token: int, status: str) -> bool:
        if token < 1:
            raise ValueError("fencing token must be positive")
        if status not in VALID_STATUSES:
            raise ValueError(f"unsupported status: {status}")

        highest_token = self.highest_tokens.get(order_id, 0)
        if token < highest_token:
            return False

        self.highest_tokens[order_id] = token
        self.statuses[order_id] = status
        return True


def demonstrate_version_ordering() -> None:
    print("1. Versioned delivery: version 2, version 1, version 2 again")
    processor = OrderProcessor()

    for event in (
        OrderEvent("order-100", 2, "PAID"),
        OrderEvent("order-100", 1, "CREATED"),
        OrderEvent("order-100", 2, "PAID"),
    ):
        print(f"  received v{event.version} {event.status}: ")
        for message in processor.receive(event):
            print(f"    {message}")

    assert processor.versions["order-100"] == 2
    assert processor.statuses["order-100"] == "PAID"
    assert processor.pending["order-100"] == {}
    print(f"  final state: v{processor.versions['order-100']} {processor.statuses['order-100']}\n")


def demonstrate_missing_event() -> None:
    print("2. Missing-event test: receive only version 3")
    processor = OrderProcessor()
    event = OrderEvent("order-200", 3, "SHIPPED")
    for message in processor.receive(event):
        print(f"  {message}")

    missing = processor.missing_versions("order-200")
    assert processor.versions.get("order-200", 0) == 0
    assert processor.statuses.get("order-200") is None
    assert missing == [1, 2]
    print(f"  current state: v0 (no status); pending versions: [3]")
    print(f"  recorded missing versions: {missing}\n")


def demonstrate_fencing_tokens() -> None:
    print("3. Stale-worker test")
    store = FencedOrderStore()
    worker_a_token = 1
    worker_b_token = 2

    print(f"  worker A receives fencing token {worker_a_token}")
    print(f"  worker B receives fencing token {worker_b_token}")
    accepted = store.write("order-300", worker_b_token, "PAID")
    print(f"  worker B update: {'ACCEPTED' if accepted else 'REJECTED'}")
    accepted = store.write("order-300", worker_a_token, "SHIPPED")
    print(f"  worker A stale update: {'ACCEPTED' if accepted else 'REJECTED'}")

    assert store.highest_tokens["order-300"] == worker_b_token
    assert store.statuses["order-300"] == "PAID"
    print(f"  final state: {store.statuses['order-300']} (token {worker_b_token})")


def main() -> None:
    demonstrate_version_ordering()
    demonstrate_missing_event()
    demonstrate_fencing_tokens()


if __name__ == "__main__":
    main()