import pandas as pd
import numpy as np
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ══════════════════════════════════════════════════════════════════════════════
# 1. LES FONCTIONS MATHÉMATIQUES
# ══════════════════════════════════════════════════════════════════════════════

def trend_detection_time(df, date_col, value_col, min_days_per_month=20, min_months=36):
    anomaly = monthly_anomalies(df, date_col, value_col, min_days_per_month)
    out = {
        "months": len(anomaly),
        "trend_decade": np.nan,
        "p_value": np.nan,
    }
    if len(anomaly) < min_months:
        return out
    t = (anomaly.index.year + (anomaly.index.month - 0.5) / 12).to_numpy(dtype=float)
    slope, intercept = np.polyfit(t, anomaly.to_numpy(dtype=float), 1)
    out["trend_decade"] = float(10 * slope)
    return out

def monthly_anomalies(df, date_col, value_col, min_days_per_month=20):
    monthly = monthly_means(df, date_col=date_col, value_col=value_col, min_days_per_month=min_days_per_month).dropna()
    if len(monthly) == 0:
        return monthly
    return monthly - monthly.groupby(monthly.index.month).transform("mean")

def monthly_means(df, date_col="dates", value_col="value", min_days_per_month=20):
    s = df.set_index(date_col)[value_col].dropna().sort_index()
    if s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    daily = s.resample("D").mean()
    monthly = daily.resample("ME").mean()
    n_days = daily.notna().resample("ME").sum()
    return monthly.where(n_days >= min_days_per_month)


# ══════════════════════════════════════════════════════════════════════════════
# 2. CODE POUR GÉNÉRER LES GRAPHIQUES
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    files = ['pzps1.csv', 'pzps3.csv', 'pzps4.csv']

    for file in files:
        file_path = os.path.join("piezo_data", file)
        
        if not os.path.exists(file_path):
            print(f"❌ Fichier introuvable : {file_path}")
            continue

        print(f"\n⏳ Traitement de {file}...")
        
        try:
            # Lecture du fichier
            df = pd.read_csv(file_path, sep=None, engine='python')
            
            # Nettoyage des noms de colonnes (enlever les espaces)
            df.columns = df.columns.str.strip()
            
            # Recherche des colonnes
            date_col = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()][0]
            temp_col = [col for col in df.columns if 'temp' in col.lower()][0]
            head_col = [col for col in df.columns if 'head' in col.lower() or 'niveau' in col.lower()][0]

            # Conversion des colonnes numériques
            df[temp_col] = pd.to_numeric(df[temp_col].astype(str).str.replace(',', '.'), errors='coerce')
            df[head_col] = pd.to_numeric(df[head_col].astype(str).str.replace(',', '.'), errors='coerce')

            # Conversion des dates
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce', dayfirst=True)
            df = df.dropna(subset=[date_col]).sort_values(by=date_col)

            print(f"   📅 Dates valides : {len(df)} lignes, du {df[date_col].min()} au {df[date_col].max()}")

            # Calcul de la tendance
            trend_results = trend_detection_time(
                df=df, 
                date_col=date_col, 
                value_col=temp_col, 
                min_days_per_month=20, 
                min_months=36
            )
            
            trend_per_decade = trend_results['trend_decade']
            
            if pd.isna(trend_per_decade):
                print(f"   ⚠️ Données insuffisantes (moins de 36 mois valides).")
                trend_text = "Inconnue"
                slope, intercept = 0, 0
                temp_monthly = None
            else:
                print(f"   ✅ Tendance : {trend_per_decade:.2f} °C/décennie")
                trend_text = f"{trend_per_decade:.2f} °C/décennie"
                temp_monthly = df.set_index(date_col)[temp_col].resample("ME").mean().dropna()
                x_trend = temp_monthly.index.year + (temp_monthly.index.month - 0.5) / 12
                slope, intercept = np.polyfit(x_trend, temp_monthly.values, 1)

            # Création de la figure Plotly
            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # Axe gauche : Niveau piézométrique
            fig.add_trace(
                go.Scatter(x=df[date_col], y=df[head_col], name="Niveau piézométrique [mNGF]", 
                           line=dict(color='blue', width=1)),
                secondary_y=False,
            )

            # Axe droit : Température (🔥 On a enlevé 'opacity' qui causait l'erreur)
            fig.add_trace(
                go.Scatter(x=df[date_col], y=df[temp_col], name="Température [°C]", 
                           line=dict(color='red', width=1)),
                secondary_y=True,
            )

            # Ligne de tendance
            if not pd.isna(trend_per_decade) and temp_monthly is not None:
                trend_y = slope * x_trend + intercept
                fig.add_trace(
                    go.Scatter(x=temp_monthly.index, y=trend_y, name="Tendance de réchauffement",
                               line=dict(color='darkred', width=3, dash='dash')),
                    secondary_y=True,
                )

            # Formatage
            fig.update_layout(
                title=f"<b>{file}</b> - Tendance : {trend_text}",
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                template="plotly_white"
            )

            fig.update_xaxes(title_text="Date")
            fig.update_yaxes(title_text="<b>Niveau piézométrique [mNGF]</b>", secondary_y=False, color='blue')
            fig.update_yaxes(title_text="<b>Température [°C]</b>", secondary_y=True, color='red')

            output_html = f"graph_{file.replace('.csv', '')}.html"
            fig.write_html(output_html)
            print(f"   ✅ Graphique sauvegardé : {output_html}")

        except Exception as e:
            print(f"   ❌ Erreur avec {file} : {e}")

    print("\n🎉 Partie 1 terminée ! Ouvrez les fichiers HTML pour voir les graphiques.")