"""
Multi-Entity Financial Variance & Consolidation Analytics Platform
==================================================================
Corporate FP&A Data Consolidation, Audit Governance, and Econometric Forecasting Engine.

Author: Rashmi Leema
License: MIT
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def load_data(data_dir: str = 'data') -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Ingest dimension tables and transaction fact records from CSV feeds.
    
    Parameters:
        data_dir (str): Relative or absolute path to the data directory.
        
    Returns:
        tuple containing (df_entities, df_gl, df_date, df_facts)
    """
    if not os.path.exists(data_dir):
        # Fallback if running from a subdirectory
        data_dir = os.path.join('..', data_dir)
        
    df_entities = pd.read_csv(os.path.join(data_dir, 'dim_legal_entity.csv'))
    df_gl = pd.read_csv(os.path.join(data_dir, 'dim_general_ledger.csv'))
    df_date = pd.read_csv(os.path.join(data_dir, 'dim_date.csv'))
    
    df_facts = pd.read_csv(os.path.join(data_dir, 'fact_financial_transactions.csv'))
    df_facts['ActualAmount'] = pd.to_numeric(df_facts['ActualAmount'])
    df_facts['BudgetAmount'] = pd.to_numeric(df_facts['BudgetAmount'])
    
    print(f"[OK] Ingested {len(df_facts):,} GL transactions across {len(df_entities)} regional operating hubs.")
    return df_entities, df_gl, df_date, df_facts


def build_consolidated_cube(
    df_facts: pd.DataFrame, 
    df_entities: pd.DataFrame, 
    df_gl: pd.DataFrame, 
    df_date: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Merge dimension metadata and materialize the multi-entity monthly analytical cube.
    
    Returns:
        tuple containing (df_merged, df_cube)
    """
    # 1. Multi-dimensional denormalization
    df_merged = (
        df_facts
        .merge(df_entities[['EntityKey', 'EntityName', 'Region', 'Currency']], on='EntityKey')
        .merge(df_gl[['AccountKey', 'AccountNumber', 'AccountName', 'AccountCategory']], on='AccountKey')
        .merge(df_date[['DateKey', 'FiscalYearMonth', 'FiscalQuarter']], on='DateKey')
    )
    
    # 2. Monthly multi-entity aggregation (Month x Region x AccountCategory)
    df_cube = (
        df_merged
        .groupby(['FiscalYearMonth', 'Region', 'AccountCategory'], as_index=False)
        [['ActualAmount', 'BudgetAmount']]
        .sum()
    )
    
    # 3. Variance metrics
    df_cube['VarianceAmount'] = df_cube['ActualAmount'] - df_cube['BudgetAmount']
    df_cube['VariancePct'] = np.where(
        df_cube['BudgetAmount'] != 0,
        (df_cube['VarianceAmount'] / df_cube['BudgetAmount']) * 100.0,
        0.0
    )
    
    # Round financial figures to the cent
    df_cube['ActualAmount'] = df_cube['ActualAmount'].round(2)
    df_cube['BudgetAmount'] = df_cube['BudgetAmount'].round(2)
    df_cube['VarianceAmount'] = df_cube['VarianceAmount'].round(2)
    df_cube['VariancePct'] = df_cube['VariancePct'].round(2)
    
    print(f"[OK] Materialized analytical summary cube: {len(df_cube)} monthly consolidated records.")
    return df_merged, df_cube


def run_audit_gate(df_facts: pd.DataFrame, df_cube: pd.DataFrame) -> bool:
    """
    Enforce zero-cent financial reconciliation between granular transactions and consolidated aggregates.
    Requirement BR-03: delta must equal $0.00.
    """
    fact_actual_total = df_facts['ActualAmount'].sum()
    cube_actual_total = df_cube['ActualAmount'].sum()
    
    fact_budget_total = df_facts['BudgetAmount'].sum()
    cube_budget_total = df_cube['BudgetAmount'].sum()
    
    actual_delta = round(fact_actual_total - cube_actual_total, 2)
    budget_delta = round(fact_budget_total - cube_budget_total, 2)
    
    print("\n" + "=" * 65)
    print("FINANCIAL AUDIT GATE: SOURCE-TO-TARGET RECONCILIATION")
    print("=" * 65)
    print(f"  Granular Transactions Actuals: ${fact_actual_total:,.2f}")
    print(f"  Consolidated Cube Actuals:     ${cube_actual_total:,.2f}")
    print(f"  Reconciliation Delta:          ${actual_delta:,.2f}")
    print(f"  Budget Reconciliation Delta:   ${budget_delta:,.2f}")
    
    if actual_delta == 0.00 and budget_delta == 0.00:
        print("  Status: [PASSED] 100% RECONCILED TO THE CENT ($0.00 DELTA)")
        print("=" * 65 + "\n")
        return True
    else:
        print("  Status: [FAILED] AUDIT EXCEPTION DETECTED")
        print("=" * 65 + "\n")
        raise ValueError(f"Reconciliation check failed with delta ${actual_delta}")


def plot_variance_distribution(df_merged: pd.DataFrame, output_path: str = 'assets/variance_distribution.png') -> None:
    """
    Generate variance distribution histogram with KDE and regional boxplot spread.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    df_expenses = df_merged[df_merged['AccountCategory'].isin(['OPEX', 'Cost of Sales'])].copy()
    df_expenses['VariancePct'] = (
        (df_expenses['ActualAmount'] - df_expenses['BudgetAmount']) / df_expenses['BudgetAmount']
    ) * 100.0

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    # 1. Histogram + KDE
    sns.histplot(df_expenses['VariancePct'], kde=True, ax=axes[0], color='#1E3E62', bins=30)
    axes[0].set_title('Expense Variance % Distribution (Normality Check)', fontsize=12, fontweight='bold')
    axes[0].set_xlabel('Variance % (Actual vs. Budget)')
    axes[0].set_ylabel('Transaction Frequency')
    axes[0].axvline(0, color='red', linestyle='--', label='Zero Variance (Budget Target)')
    axes[0].legend()

    # 2. Regional Boxplot
    sns.boxplot(
        data=df_expenses, 
        x='Region', 
        y='VariancePct', 
        hue='Region',
        legend=False,
        ax=axes[1], 
        palette=['#64B5F6', '#81C784', '#FFB74D']
    )
    axes[1].set_title('Expense Variance Spread by Operating Hub', fontsize=12, fontweight='bold')
    axes[1].set_xlabel('Operating Hub')
    axes[1].set_ylabel('Variance %')
    axes[1].axhline(0, color='red', linestyle='--', alpha=0.7)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Saved statistical distribution plot to {output_path}")


def generate_revenue_forecast(
    df_merged: pd.DataFrame, 
    output_path: str = 'assets/revenue_forecast.png'
) -> dict:
    """
    Fit linear regression trend on historical monthly revenue and project Q1 2026 with confidence bands.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 1. Aggregate monthly actual revenue
    df_monthly_rev = (
        df_merged[df_merged['AccountCategory'] == 'Revenue']
        .groupby('FiscalYearMonth', as_index=False)['ActualAmount']
        .sum()
    )

    t = np.arange(1, len(df_monthly_rev) + 1)
    revenue = df_monthly_rev['ActualAmount'].values

    # 2. Regression fit
    slope, intercept = np.polyfit(t, revenue, 1)
    fitted_trend = slope * t + intercept

    # 3. Forecast Q1 2026 (t = 25, 26, 27)
    future_t = np.array([25, 26, 27])
    future_months = ['2026-01', '2026-02', '2026-03']
    forecast = slope * future_t + intercept

    # 4. 95% Confidence / Prediction interval
    residuals = revenue - fitted_trend
    std_err = np.std(residuals)

    # 5. Plotting
    plt.figure(figsize=(14, 6))
    plt.plot(
        df_monthly_rev['FiscalYearMonth'], 
        revenue / 1e6, 
        marker='o', 
        color='#1E3E62', 
        linewidth=2, 
        label='Historical Actuals (2024–2025)'
    )
    plt.plot(
        df_monthly_rev['FiscalYearMonth'], 
        fitted_trend / 1e6, 
        color='#64B5F6', 
        linestyle='--', 
        linewidth=1.5, 
        label=f'Trend Line (Slope: ${slope:,.0f}/mo)'
    )
    plt.plot(
        future_months, 
        forecast / 1e6, 
        marker='s', 
        color='#E57373', 
        linestyle='--', 
        linewidth=2.5, 
        label='Q1 2026 Forecast'
    )
    plt.fill_between(
        future_months, 
        (forecast - 1.96 * std_err) / 1e6, 
        (forecast + 1.96 * std_err) / 1e6, 
        color='#E57373', 
        alpha=0.2, 
        label='95% Prediction Interval'
    )

    plt.title('Monthly Revenue Momentum & Q1 2026 Predictive Forecast', fontsize=14, fontweight='bold')
    plt.xlabel('Fiscal Month')
    plt.ylabel('Monthly Revenue ($ Millions USD)')
    plt.xticks(rotation=45)
    plt.legend(loc='upper left')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    
    print(f"[OK] Saved revenue forecast chart to {output_path}")
    
    return {
        'slope': slope,
        'forecast': dict(zip(future_months, forecast)),
        'std_err': std_err
    }


def main():
    print("\n" + "=" * 65)
    print("STARTING FINANCIAL CONSOLIDATION & ANALYTICS PIPELINE")
    print("=" * 65)
    
    # 1. Ingest
    df_entities, df_gl, df_date, df_facts = load_data()
    
    # 2. Consolidate
    df_merged, df_cube = build_consolidated_cube(df_facts, df_entities, df_gl, df_date)
    
    # 3. Audit Gate
    run_audit_gate(df_facts, df_cube)
    
    # 4. Statistical Models & Visualizations
    plot_variance_distribution(df_merged)
    forecast_results = generate_revenue_forecast(df_merged)
    
    # 5. Export clean consolidated output
    out_csv = 'data/fact_monthly_financial_summary.csv'
    df_cube.to_csv(out_csv, index=False)
    print(f"[OK] Exported consolidated analytical summary to {out_csv}")
    print("\n[SUCCESS] Pipeline completed with zero errors.\n")


if __name__ == '__main__':
    main()
