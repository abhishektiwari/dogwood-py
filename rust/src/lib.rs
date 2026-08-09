use dogwood_language::{
    replay_log, Authorizer, Decision, Event, LoweredPolicySet, PolicySchema, ServiceSchema,
    Validator,
};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;

#[pyclass(unsendable)]
struct NativeAuthorizer {
    authorizer: Authorizer,
}

#[pymethods]
impl NativeAuthorizer {
    #[new]
    #[pyo3(signature = (policy_source, policy_schema_source, event_schema_source=None))]
    fn new(
        policy_source: &str,
        policy_schema_source: &str,
        event_schema_source: Option<&str>,
    ) -> PyResult<Self> {
        let policies = lower(policy_source, policy_schema_source, event_schema_source)?;
        Ok(Self {
            authorizer: Authorizer::new(policies),
        })
    }

    fn authorize_request(
        &mut self,
        action: &str,
        principal: &str,
        resource: &str,
        input_json: &str,
    ) -> PyResult<String> {
        let event = request_event(action, principal, resource, input_json)?;
        decision_string(self.authorizer.is_authorized(&event))
    }
}

#[pyfunction]
fn native_available() -> bool {
    true
}

#[pyfunction]
#[pyo3(signature = (policy_source, policy_schema_source, event_schema_source=None))]
fn lower_to_cedar(
    policy_source: &str,
    policy_schema_source: &str,
    event_schema_source: Option<&str>,
) -> PyResult<String> {
    let policies = lower(policy_source, policy_schema_source, event_schema_source)?;
    policies
        .as_cedar()
        .to_string()
        .parse()
        .map_err(|err| PyRuntimeError::new_err(format!("failed to render Cedar policies: {err}")))
}

#[pyfunction]
#[pyo3(signature = (policy_source, policy_schema_source, event_schema_source=None))]
fn cedar_schema(
    policy_source: &str,
    policy_schema_source: &str,
    event_schema_source: Option<&str>,
) -> PyResult<String> {
    let policies = lower(policy_source, policy_schema_source, event_schema_source)?;
    policies
        .cedar_schema_str()
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[pyo3(signature = (policy_source, policy_schema_source, event_schema_source=None))]
fn validate_policy(
    py: Python<'_>,
    policy_source: &str,
    policy_schema_source: &str,
    event_schema_source: Option<&str>,
) -> PyResult<PyObject> {
    let policies = lower(policy_source, policy_schema_source, event_schema_source)?;
    let result = Validator::new().validate(&policies);
    let out = PyDict::new_bound(py);
    out.set_item("passed", result.validation_passed())?;
    out.set_item(
        "errors",
        result
            .validation_errors()
            .map(|err| err.to_string())
            .collect::<Vec<_>>(),
    )?;
    out.set_item(
        "warnings",
        result
            .validation_warnings()
            .map(|warning| warning.to_string())
            .collect::<Vec<_>>(),
    )?;
    Ok(out.into())
}

#[pyfunction]
#[pyo3(signature = (policy_source, policy_schema_source, trace_source, event_schema_source=None))]
fn replay(
    policy_source: &str,
    policy_schema_source: &str,
    trace_source: &str,
    event_schema_source: Option<&str>,
) -> PyResult<String> {
    let policies = lower(policy_source, policy_schema_source, event_schema_source)?;
    replay_log(policies, trace_source).map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

#[pyfunction]
#[pyo3(signature = (
    policy_source,
    policy_schema_source,
    action,
    principal,
    resource,
    input_json,
    event_schema_source=None
))]
fn authorize_request(
    policy_source: &str,
    policy_schema_source: &str,
    action: &str,
    principal: &str,
    resource: &str,
    input_json: &str,
    event_schema_source: Option<&str>,
) -> PyResult<String> {
    let policies = lower(policy_source, policy_schema_source, event_schema_source)?;
    let mut authorizer = Authorizer::new(policies);
    let event = request_event(action, principal, resource, input_json)?;
    decision_string(authorizer.is_authorized(&event))
}

fn request_event(
    action: &str,
    principal: &str,
    resource: &str,
    input_json: &str,
) -> PyResult<Event> {
    let mut builder = Event::builder(action, "request")
        .principal(principal)
        .resource(resource);

    let input: serde_json::Value =
        serde_json::from_str(input_json).map_err(|err| PyValueError::new_err(err.to_string()))?;
    let object = input
        .as_object()
        .ok_or_else(|| PyValueError::new_err("input_json must be a JSON object"))?;
    for (name, value) in object {
        let value = json_to_dogwood(value)?;
        builder = builder
            .field("input", name, value.clone())
            .request_context("input", name, value);
    }

    Ok(builder.build())
}

fn decision_string(response: Option<dogwood_language::Response>) -> PyResult<String> {
    match response {
        Some(response) if response.decision() == Decision::Allow => Ok("Allow".to_string()),
        Some(_) => Ok("Deny".to_string()),
        None => Ok("NoDecision".to_string()),
    }
}

fn lower(
    policy_source: &str,
    policy_schema_source: &str,
    event_schema_source: Option<&str>,
) -> PyResult<LoweredPolicySet> {
    let service = match event_schema_source {
        Some(source) => ServiceSchema::builder()
            .event_schema_str(source)
            .build()
            .map_err(|err| PyRuntimeError::new_err(err.to_string()))?,
        None => ServiceSchema::defaults(),
    };
    let schema = PolicySchema::from_cedarschema_str(policy_schema_source)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))?;
    LoweredPolicySet::from_str(policy_source, &service, &schema)
        .map_err(|err| PyRuntimeError::new_err(err.to_string()))
}

fn json_to_dogwood(value: &serde_json::Value) -> PyResult<dogwood_language::Value> {
    match value {
        serde_json::Value::Null => Ok(dogwood_language::Value::Null),
        serde_json::Value::Bool(v) => Ok(dogwood_language::Value::Bool(*v)),
        serde_json::Value::Number(v) => {
            if let Some(i) = v.as_i64() {
                Ok(dogwood_language::Value::Int(i))
            } else {
                Ok(dogwood_language::Value::Decimal(v.to_string()))
            }
        }
        serde_json::Value::String(v) => Ok(dogwood_language::Value::String(v.clone())),
        serde_json::Value::Array(values) => values
            .iter()
            .map(json_to_dogwood)
            .collect::<PyResult<Vec<_>>>()
            .map(dogwood_language::Value::Array),
        serde_json::Value::Object(values) => values
            .iter()
            .map(|(key, value)| Ok((key.clone(), json_to_dogwood(value)?)))
            .collect::<PyResult<std::collections::BTreeMap<_, _>>>()
            .map(dogwood_language::Value::Object),
    }
}

#[pymodule]
fn _dogwood_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NativeAuthorizer>()?;
    m.add_function(wrap_pyfunction!(native_available, m)?)?;
    m.add_function(wrap_pyfunction!(lower_to_cedar, m)?)?;
    m.add_function(wrap_pyfunction!(cedar_schema, m)?)?;
    m.add_function(wrap_pyfunction!(validate_policy, m)?)?;
    m.add_function(wrap_pyfunction!(replay, m)?)?;
    m.add_function(wrap_pyfunction!(authorize_request, m)?)?;
    Ok(())
}
