use bus::{Bus, Event};
use futures::executor::block_on;
use serde::Serialize;

#[derive(Debug, Serialize, PartialEq)]
struct Spoke {
    seat: u32,
    text: String,
}
impl Event for Spoke {
    const NAME: &'static str = "test.spoke";
}

#[derive(Debug, Serialize, PartialEq)]
struct Passed {
    seat: u32,
}
impl Event for Passed {
    const NAME: &'static str = "test.passed";
}

#[test]
fn typed_subscribers_receive_only_their_type_in_order() {
    let bus = Bus::new();
    let mut spoken = bus.subscribe::<Spoke>();
    bus.publish(Spoke { seat: 1, text: "a".into() });
    bus.publish(Passed { seat: 2 });
    bus.publish(Spoke { seat: 3, text: "b".into() });

    block_on(async {
        let first = spoken.recv().await.unwrap();
        let second = spoken.recv().await.unwrap();
        assert_eq!((first.seq, first.event.seat), (1, 1));
        assert_eq!((second.seq, second.event.seat), (3, 3));
    });
}

#[test]
fn a_tap_sees_every_type_in_global_order_with_json() {
    let bus = Bus::new();
    let mut tap = bus.tap();
    bus.publish(Passed { seat: 2 });
    bus.publish(Spoke { seat: 1, text: "hello".into() });

    block_on(async {
        let first = tap.recv().await.unwrap();
        let second = tap.recv().await.unwrap();
        assert_eq!((first.seq, first.name), (1, "test.passed"));
        assert_eq!((second.seq, second.name), (2, "test.spoke"));
        assert_eq!(second.to_json().unwrap(), serde_json::json!({"seat": 1, "text": "hello"}));
        assert_eq!(second.downcast::<Spoke>().unwrap().text, "hello");
        assert!(second.downcast::<Passed>().is_none());
    });
}

#[test]
fn publishing_never_blocks_on_unread_or_dropped_subscribers() {
    let bus = Bus::new();
    let mut unread = bus.subscribe::<Passed>();
    drop(bus.subscribe::<Passed>());
    drop(bus.tap());

    for seat in 0..10_000 {
        bus.publish(Passed { seat });
    }

    // The unread subscriber kept everything; nothing was dropped.
    block_on(async {
        for expected in 0..10_000 {
            assert_eq!(unread.recv().await.unwrap().event.seat, expected);
        }
    });
}

#[test]
fn concurrent_publishers_produce_one_consistent_order() {
    let bus = Bus::new();
    let mut a = bus.tap();
    let mut b = bus.tap();
    let workers: Vec<_> = (0..4)
        .map(|w| {
            let bus = bus.clone();
            std::thread::spawn(move || {
                for i in 0..500 {
                    bus.publish(Passed { seat: w * 1000 + i });
                }
            })
        })
        .collect();
    workers.into_iter().for_each(|w| w.join().unwrap());

    block_on(async {
        for expected in 1..=2000 {
            let (x, y) = (a.recv().await.unwrap(), b.recv().await.unwrap());
            assert_eq!(x.seq, expected);
            assert_eq!(y.seq, expected);
            assert_eq!(x.downcast::<Passed>(), y.downcast::<Passed>());
        }
    });
}
