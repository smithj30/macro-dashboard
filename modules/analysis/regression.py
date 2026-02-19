"""
Statistical analysis: OLS regression, rolling correlation.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm


# ---------------------------------------------------------------------------
# OLS Regression
# ---------------------------------------------------------------------------

def run_ols(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
    add_constant: bool = True,
) -> dict:
    """
    Run OLS regression.

    Parameters
    ----------
    df          : DataFrame containing the series (aligned, numeric)
    dep_var     : name of the dependent variable column
    indep_vars  : list of independent variable column names
    add_constant: whether to add an intercept term

    Returns
    -------
    dict with keys:
        summary_html : HTML string of the statsmodels summary
        params       : pd.Series of coefficients
        rsquared     : float
        rsquared_adj : float
        pvalues      : pd.Series
        fstatistic   : float
        fpvalue      : float
        residuals    : pd.Series (indexed like df)
        fitted       : pd.Series
        model_result : the raw statsmodels RegressionResultsWrapper
    """
    cols = [dep_var] + indep_vars
    sub = df[cols].dropna()

    y = sub[dep_var]
    X = sub[indep_vars]

    if add_constant:
        X = sm.add_constant(X)

    model = sm.OLS(y, X).fit()

    residuals = pd.Series(model.resid, index=sub.index, name="residuals")
    fitted = pd.Series(model.fittedvalues, index=sub.index, name="fitted")

    return {
        "summary_html": model.summary().as_html(),
        "params": model.params,
        "rsquared": model.rsquared,
        "rsquared_adj": model.rsquared_adj,
        "pvalues": model.pvalues,
        "fstatistic": model.fvalue,
        "fpvalue": model.f_pvalue,
        "residuals": residuals,
        "fitted": fitted,
        "nobs": int(model.nobs),
        "model_result": model,
    }


def format_ols_table(result: dict) -> pd.DataFrame:
    """
    Return a clean coefficient table from OLS results.
    Columns: coefficient, std_error, t_stat, p_value, significant.
    """
    m = result["model_result"]
    table = pd.DataFrame({
        "coefficient": m.params,
        "std_error": m.bse,
        "t_stat": m.tvalues,
        "p_value": m.pvalues,
    })
    table["significant"] = table["p_value"] < 0.05
    return table.round(4)


# ---------------------------------------------------------------------------
# Rolling Correlation
# ---------------------------------------------------------------------------

def rolling_correlation(
    s1: pd.Series,
    s2: pd.Series,
    window: int,
) -> pd.Series:
    """
    Compute rolling Pearson correlation between two series.

    Both series are aligned on their index before computation.
    Returns a Series with the same index, named 'rolling_corr'.
    """
    combined = pd.concat([s1, s2], axis=1).dropna()
    if combined.shape[1] < 2:
        raise ValueError("Could not align both series on a common date index.")

    col_a, col_b = combined.columns[0], combined.columns[1]
    result = combined[col_a].rolling(window=window).corr(combined[col_b])
    result.name = f"Rolling {window}-period Corr ({s1.name} vs {s2.name})"
    return result


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Return Pearson correlation matrix for all numeric columns in df."""
    numeric = df.select_dtypes(include=[np.number])
    return numeric.corr(method="pearson")
