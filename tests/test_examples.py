from dogwood import Authorizer, Event, LoweredPolicySet, PolicySchema, ServiceSchema, parse_trace, replay_log


def test_event_builder_and_basic_authorization():
    source = '''
    @id("sell_small_only")
    permit (principal, action == Drupe::Action::"SellShares", resource)
    when { context.input.shares <= 50 };
    '''
    policies = LoweredPolicySet.from_str(source, ServiceSchema.defaults(), PolicySchema(""))
    event = (
        Event.builder('Drupe::Action::"SellShares"', "request")
        .principal('Drupe::OAuthUser::"alice"')
        .resource('Drupe::Gateway::"gw1"')
        .field("input", "shares", 50)
        .request_context("input", "shares", 50)
        .build()
    )
    assert Authorizer(policies).is_authorized(event).allowed()


def test_forbid_overrides_and_unless():
    source = '''
    @id("forbid_large_except_amzn")
    forbid (principal, action == Drupe::Action::"SellShares", resource)
    when { context.input.shares > 100 }
    unless { context.input.stock == "AMZN" };
    '''
    trace = '''
    @0 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { shares: 500, stock: "MSFT" }) Drupe::Action::"SellShares"::request(input: { shares: 500, stock: "MSFT" })
    @1 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { shares: 500, stock: "AMZN" }) Drupe::Action::"SellShares"::request(input: { shares: 500, stock: "AMZN" })
    '''
    policies = LoweredPolicySet.from_str(source)
    assert replay_log(policies, trace).splitlines() == [
        "@0 (time point 0): false",
        "@1 (time point 1): false",
    ]


def test_formerly_within_temporal():
    source = '''
    @id("read_after_login")
    permit (principal, action == Drupe::Action::"Read", resource)
    when temporal {
        formerly within 1h Drupe::Action::"Login"::response{ input.user: context.input.user }
    };
    '''
    trace = '''
    @0 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Login"::request(input: { user: "alice" })
    @5 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Login"::response(input: { user: "alice" })
    @10 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Read"::request(input: { user: "alice" })
    @7200 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Read"::request(input: { user: "alice" })
    '''
    policies = LoweredPolicySet.from_str(source)
    assert len(parse_trace(trace)) == 4
    assert replay_log(policies, trace).splitlines() == [
        "@0 (time point 0): false",
        "@10 (time point 2): true",
        "@7200 (time point 3): false",
    ]
