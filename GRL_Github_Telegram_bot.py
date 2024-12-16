from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import os

# Obtener el token de la variable de entorno
TOKEN = os.getenv("TOKEN")

# Variables globales
datos = {}
estado = {}

# Inicio del bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Bienvenido al bot de Gestión de Riesgo en Entrada (GRE) para operaciones LONG!\n"
        "Por favor, dime el precio de entrada."
    )
    estado[update.effective_user.id] = "precio_entrada"

# Procesar mensajes
async def procesar_datos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text.strip().lower().replace(",", ".")
    
    try:
        if estado.get(user_id) == "precio_entrada":
            datos[user_id] = {"tipo_operacion": "long", "precio_entrada": float(texto)}
            estado[user_id] = "capital_total"
            await update.message.reply_text("Dime el capital total de la cuenta (USD).")
        elif estado.get(user_id) == "capital_total":
            datos[user_id]["capital_total"] = float(texto)
            estado[user_id] = "porcentaje_riesgo"
            await update.message.reply_text("Dime el porcentaje de riesgo sobre el capital total.")
        elif estado.get(user_id) == "porcentaje_riesgo":
            datos[user_id]["porcentaje_riesgo"] = float(texto)
            estado[user_id] = "porcentaje_stop_loss"
            await update.message.reply_text("Dime el porcentaje de stop loss basado en el precio de entrada.")
        elif estado.get(user_id) == "porcentaje_stop_loss":
            datos[user_id]["porcentaje_stop_loss"] = float(texto)
            estado[user_id] = "niveles_recompra"
            await update.message.reply_text("Dime la cantidad de niveles de recompra.")
        elif estado.get(user_id) == "niveles_recompra":
            datos[user_id]["niveles_recompra"] = int(texto)
            estado[user_id] = "porcentaje_recompra"
            await update.message.reply_text(
                "Dime el porcentaje de diferencia entre los niveles de recompra.\n"
                "Si prefieres la distribución predeterminada, escribe `0`."
            )
        elif estado.get(user_id) == "porcentaje_recompra":
            datos[user_id]["porcentaje_recompra"] = float(texto)
            estado[user_id] = "niveles_take_profit"
            await update.message.reply_text("Dime la cantidad de niveles de take profit.")
        elif estado.get(user_id) == "niveles_take_profit":
            datos[user_id]["niveles_take_profit"] = int(texto)
            estado[user_id] = "porcentaje_take_profit"
            await update.message.reply_text("Dime el porcentaje de diferencia entre niveles de take profit.")
        elif estado.get(user_id) == "porcentaje_take_profit":
            datos[user_id]["porcentaje_take_profit"] = float(texto)
            estado[user_id] = None
            await calcular_resultados(update, datos[user_id])
        else:
            await update.message.reply_text("Algo salió mal. Intenta de nuevo con /start.")
    except ValueError as e:
        await update.message.reply_text(f"Error: {e}. Por favor, introduce un número válido.")
    except Exception as e:
        await update.message.reply_text("Ocurrió un error inesperado. Por favor, inténtalo de nuevo más tarde.")

# Modificación en el cálculo de niveles de recompra
async def calcular_resultados(update: Update, datos: dict):
    try:
        # Datos ingresados
        precio_entrada = datos["precio_entrada"]
        capital_total = datos["capital_total"]
        porcentaje_riesgo = datos["porcentaje_riesgo"]
        porcentaje_stop_loss = datos["porcentaje_stop_loss"]
        niveles_recompra = datos["niveles_recompra"]
        porcentaje_recompra = datos["porcentaje_recompra"]  # Nuevo
        niveles_take_profit = datos["niveles_take_profit"]
        porcentaje_take_profit = datos["porcentaje_take_profit"]

        # Calcular Stop Loss Global
        stop_loss_global = precio_entrada * (1 - (porcentaje_stop_loss / 100))
        if stop_loss_global >= precio_entrada:
            raise ValueError("El Stop Loss Global para una operación long debe ser menor que el precio de entrada.")

        # Riesgo Máximo Permitido
        riesgo_maximo = capital_total * (porcentaje_riesgo / 100)

        # Distribuir riesgo entre la entrada inicial y las recompras
        riesgo_por_nivel = round(riesgo_maximo / (niveles_recompra + 1), 6)

        # Tokens iniciales
        diferencia_stop_loss = abs(precio_entrada - stop_loss_global)
        tokens_iniciales = round(riesgo_por_nivel / diferencia_stop_loss, 6)

        # Distribución de niveles de recompra
        if porcentaje_recompra > 0:  # Opción personalizada
            precios_recompra = [
                round(precio_entrada * (1 - (porcentaje_recompra / 100) * i), 6)
                for i in range(1, niveles_recompra + 1)
            ]
        else:  # Distribución predeterminada
            primer_nivel_recompra = precio_entrada * 0.985  # 1.5% por debajo de la entrada
            ultimo_nivel_recompra = stop_loss_global * 1.0075  # 0.75% por encima del stop loss global
            precios_recompra = [
                round(primer_nivel_recompra - i * (primer_nivel_recompra - ultimo_nivel_recompra) / (niveles_recompra - 1), 6)
                for i in range(niveles_recompra)
            ]
        
        tokens_recompra = [
            round(riesgo_por_nivel / abs(precio - stop_loss_global), 6) 
            for precio in precios_recompra
        ]

        # Niveles de Take Profit
        precios_take_profit = [
            round(precio_entrada * (1 + i * (porcentaje_take_profit / 100)), 6)
            for i in range(1, niveles_take_profit + 1)
        ]
        tokens_take_profit = [
            round(tokens_iniciales * i / sum(range(1, niveles_take_profit + 1)), 6)
            for i in range(1, niveles_take_profit + 1)
        ]

        # Resultados
        resultados = (
            f"*Resultados de Gestión de Riesgo en Entrada (GRE - LONG):*\n\n"
            f"*Datos Ingresados:*\n"
        )
        for clave, valor in datos.items():
            resultados += f"- {clave.capitalize().replace('_', ' ')}: {valor}\n"
        resultados += f"\n*Riesgo Máximo Permitido:* {riesgo_maximo:.2f} USD\n"
        resultados += f"*Cantidad Inicial de Tokens:* {tokens_iniciales}\n"
        resultados += f"\n*Stop Loss Global:* {stop_loss_global}\n\n"
        resultados += "*Niveles de Recompra:*\n"
        for i, (precio, tokens) in enumerate(zip(precios_recompra, tokens_recompra)):
            resultados += f"- Nivel {i + 1}: Precio {precio}, Tokens {tokens}\n"
        resultados += "\n*Niveles de Take Profit:*\n"
        for i, (precio, tokens) in enumerate(zip(precios_take_profit, tokens_take_profit)):
            resultados += f"- Nivel {i + 1}: Precio {precio}, Tokens {tokens}\n"

        # Enviar resultados
        await update.message.reply_text(resultados, parse_mode="Markdown")

    except ValueError as ve:
        await update.message.reply_text(f"Error en la validación: {ve}")
    except Exception as e:
        await update.message.reply_text(f"Error al calcular resultados: {e}")

# Configuración del bot
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_datos))

print("Bot GRE para operaciones LONG en ejecución...")
app.run_polling()
