use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

#[pyfunction]
fn flatten(py: Python<'_>, obj: PyObject, sep: &str) -> PyResult<PyObject> {
    let out = PyDict::new(py);
    let obj_bound = obj.bind(py);
    
    process_object(&obj_bound, "", sep, &out)?;
    Ok(out.into())
}

fn process_object<'py>(
    obj: &Bound<'py, PyAny>,
    prefix: &str,
    sep: &str,
    result: &Bound<'py, PyDict>,
) -> PyResult<()> {
    if let Ok(dict) = obj.downcast::<PyDict>() {
        for (key, value) in dict.iter() {
            let new_key = if prefix.is_empty() {
                key.to_string()
            } else {
                format!("{}{}{}", prefix, sep, key.to_string())
            };
            process_object(&value, &new_key, sep, result)?;
        }
    } else if let Ok(list) = obj.downcast::<PyList>() {
        for (i, item) in list.iter().enumerate() {
            let new_key = if prefix.is_empty() {
                i.to_string()
            } else {
                format!("{}{}{}", prefix, sep, i)
            };
            process_object(&item, &new_key, sep, result)?;
        }
    } else {
        result.set_item(prefix, obj)?;
    }
    Ok(())
}

#[pymodule]
fn jonq_fast(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(flatten, m)?)?;
    Ok(())
}