-- Ajustes de Pandoc antes de pasar el Markdown ensamblado a Typst.
--
-- 1. Bloques ::: {.shift levels="N"} :::
--    build.py envuelve así cada archivo incluido bajo un nivel más profundo.
--    Aquí se desplazan sus encabezados SIN el tope de 6 niveles de Markdown,
--    para que las secciones internas de los módulos no se aplanen.
-- 2. <br> dentro de celdas de tabla
--    El profesorado lo usa para partir líneas en tablas de RA/UD. Typst no
--    entiende HTML, así que se convierte en salto de línea. (Los <hr> ya
--    llegan convertidos en <br> desde build.py: Pandoc los descarta.)
-- 3. Títulos de módulo (en el nivel `module-level` del front matter)
--    Se quita el prefijo "Módulo Profesional." que cada profesor escribe a su
--    manera: la plantilla ya pone la etiqueta "Módulo profesional" encima.
-- 6. Alineación de tablas
--    Cada profesor centraba columnas a su manera (:---:). Se ignora lo escrito
--    y se aplica una sola regla: columnas de datos cortos (RA1, 18 %, 1.º,
--    códigos…) centradas; columnas con texto, a la izquierda.
-- 7. Cabecera de tabla usada como título
--    Si la fila de cabecera solo tiene texto en la primera celda y la primera
--    fila del cuerpo está completa, la primera es un título y la segunda la
--    cabecera real: el título pasa a ser el rótulo de la tabla.
-- 8. Párrafos que empiezan por una letra en negrita (**a)** …)
--    Son las listas de objetivos y criterios (ver build.py). Se maquetan con
--    sangría francesa para que el texto quede alineado tras la letra.
-- 9. Símbolos
--    Emojis decorativos (📋, 🏢…) fuera; las marcas de verificación (✅, ✔)
--    se unifican en ✓ para que todas se vean igual.
-- 10. Porcentajes
--    "0,67 %" no debe partirse entre líneas: el espacio antes de % pasa a
--    ser no separable.
-- 5. Salto de página antes de cada módulo
--    Cada módulo empieza en página nueva, SALVO que venga justo detrás de
--    otro título (p. ej. "Módulos profesionales", o la enseñanza y el curso en
--    el resumen general): así no quedan páginas con un título suelto.
-- 4. Anchos de columna
--    Pandoc fija anchos según los guiones de la fila separadora, lo que deja
--    columnas de 3 letras. Se recalculan según el texto de cada columna
--    (ver regla 6, que se aplica en la misma función).

local module_level = 5

local function read_meta(meta)
  if meta["module-level"] ~= nil then
    module_level = tonumber(pandoc.utils.stringify(meta["module-level"])) or 5
  end
  return nil
end

local function shift_block(div)
  if not div.classes:includes("shift") then
    return nil
  end
  local levels = tonumber(div.attributes["levels"]) or 0
  return div.content:walk({
    Header = function(header)
      header.level = header.level + levels
      return header
    end,
  })
end

local function html_break(raw)
  if raw.format:match("html") and raw.text:match("^<br") then
    return pandoc.LineBreak()
  end
  return nil
end

local function module_title(header)
  if module_level == 0 or header.level ~= module_level then
    return nil
  end
  local text = pandoc.utils.stringify(header.content)
  local stripped = text:gsub("^%s*[Mm]ódulo [Pp]rofesional%s*[%.:%-–]?%s*", "")
  if stripped ~= text then
    header.content = pandoc.Inlines(stripped)
  end
  return header
end

local SHORT_CELL = 14  -- caracteres

local function cell_text(cell)
  return pandoc.utils.stringify(cell.contents)
end

local function row_texts(row)
  local out = {}
  for _, cell in ipairs(row.cells) do
    table.insert(out, cell_text(cell))
  end
  return out
end

-- Regla 7: fila de título en la cabecera
local function title_row_to_caption(tbl)
  if #tbl.head.rows ~= 1 or #tbl.bodies == 0 or #tbl.bodies[1].body == 0 then
    return
  end
  local head = row_texts(tbl.head.rows[1])
  local first = row_texts(tbl.bodies[1].body[1])
  if head[1] == "" then return end
  for i = 2, #head do
    if head[i] ~= "" then return end
  end
  for i = 1, #first do
    if first[i] == "" then return end
  end
  tbl.caption = { long = { pandoc.Plain(pandoc.Inlines(head[1])) } }
  tbl.head.rows = { tbl.bodies[1].body[1] }
  tbl.bodies[1].body:remove(1)
end

local function tables(tbl)
  title_row_to_caption(tbl)
  -- En las vistas con una columna RA, repetir RA2. delante de cada letra
  -- ensancha las celdas sin aportar información. La fuente mantiene los códigos.
  local head = #tbl.head.rows > 0 and row_texts(tbl.head.rows[1]) or {}
  if head[1] == "RA" then
    for _, body in ipairs(tbl.bodies) do
      for _, row in ipairs(body.body) do
        for i, cell in ipairs(row.cells) do
          if head[i] == "Criterios" or head[i] == "Criterios en centro" or head[i] == "Criterios en empresa" then
            local original = cell_text(cell)
            local prefix = cell_text(row.cells[1]) .. "."
            if original:find(prefix, 1, true) then
              local compact = original:gsub("RA%d+%.", "")
              cell.contents = pandoc.Blocks({pandoc.Plain(pandoc.Inlines(compact))})
            end
          end
        end
      end
    end
  end
  local ncols = #tbl.colspecs
  local longest = {}
  for i = 1, ncols do longest[i] = 0 end
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do
      for i, cell in ipairs(row.cells) do
        if i <= ncols then
          -- los <br> parten la celda: cuenta el trozo más largo
          for piece in (cell_text(cell) .. "\n"):gmatch("(.-)\n") do
            longest[i] = math.max(longest[i], utf8.len(piece) or #piece)
          end
        end
      end
    end
  end
  -- Ancho: cada columna pide según su texto más largo (con tope, para que
  -- una celda enorme no se lo coma todo) y nunca menos que la palabra más
  -- larga de su cabecera, que no debe partirse.
  -- La cabecera ya se ha leído antes de compactar los códigos.
  local weights, total = {}, 0
  for i = 1, ncols do
    local word = 0
    for w in (head[i] or ""):gmatch("%S+") do word = math.max(word, utf8.len(w) or #w) end
    weights[i] = math.max(math.min(longest[i], 45), word, 3) + 3  -- +3: margen de celda
    total = total + weights[i]
  end
  for i, spec in ipairs(tbl.colspecs) do
    local align = longest[i] <= SHORT_CELL and pandoc.AlignCenter or pandoc.AlignLeft
    tbl.colspecs[i] = { align, weights[i] / total }
  end
  -- Las celdas heredan la alineación de su columna
  local function reset(rows)
    for _, row in ipairs(rows) do
      for _, cell in ipairs(row.cells) do cell.alignment = pandoc.AlignDefault end
    end
  end
  reset(tbl.head.rows)
  for _, body in ipairs(tbl.bodies) do reset(body.body) end
  -- Mantener juntas las tablas breves de UD y de pesos; las de criterios
  -- siguen partiéndose y repiten su cabecera en la página siguiente.
  local rows = 0
  local length = 0
  for _, body in ipairs(tbl.bodies) do
    rows = rows + #body.body
    for _, row in ipairs(body.body) do
      for _, cell in ipairs(row.cells) do length = length + #cell_text(cell) end
    end
  end
  local short = head[1] == "UD" or (head[1] == "RA" and (head[2] or ""):match("^Peso"))
  if short and rows <= 8 and length < 1200 then
    return pandoc.Div({pandoc.RawBlock("typst", "#block(breakable: false)["),
      tbl, pandoc.RawBlock("typst", "]")})
  end
  return tbl
end

-- Regla 8: párrafo con letra en negrita → sangría francesa
local function letter_paragraph(para)
  -- Los rótulos de las dos tablas de evaluación deben acompañar a su tabla.
  if #para.content == 1 and para.content[1].t == "Strong" then
    local body = pandoc.write(pandoc.Pandoc({pandoc.Plain(para.content)}), "typst"):gsub("%s+$", "")
    return pandoc.RawBlock("typst", "#block(sticky: true)[" .. body .. "]")
  end
  local first = para.content[1]
  if not first or first.t ~= "Strong" then return nil end
  local label = pandoc.utils.stringify(first)
  -- (la ñ ocupa dos bytes: en Lua no cabe en una clase [a-z])
  local letter = label:match("^(.+)[%.%)]$")
  if not letter or not (letter:match("^[a-z]$") or letter == "ñ") then return nil end
  local body = pandoc.write(pandoc.Pandoc({ pandoc.Plain(para.content) }), "typst")
  return pandoc.RawBlock("typst", "#par(hanging-indent: 1.3em)[" .. body:gsub("%s+$", "") .. "]")
end

-- Regla 9: símbolos
local CHECKS = { [0x2705] = true, [0x2714] = true, [0x2611] = true }
local function symbols(str)
  local out, changed = {}, false
  for _, cp in utf8.codes(str.text) do
    if CHECKS[cp] then
      table.insert(out, utf8.char(0x2713)); changed = true
    elseif (cp >= 0x1F300 and cp <= 0x1FAFF) or cp == 0xFE0F then
      changed = true  -- emoji decorativo: fuera
    else
      table.insert(out, utf8.char(cp))
    end
  end
  if not changed then return nil end
  local text = table.concat(out)
  if text == "" then return {} end
  str.text = text
  return str
end

local function percent_nbsp(inlines)
  local out = pandoc.Inlines({})
  local i = 1
  while i <= #inlines do
    local a, b, c = inlines[i], inlines[i + 1], inlines[i + 2]
    if a and b and c and a.t == "Str" and a.text:match("%d$") and b.t == "Space"
        and c.t == "Str" and c.text:match("^%%") then
      out:insert(pandoc.Str(a.text .. "\u{00A0}" .. c.text))
      i = i + 3
    else
      out:insert(a)
      i = i + 1
    end
  end
  return out
end

local function pending_inlines(inlines)
  local out, i = pandoc.Inlines({}), 1
  while i <= #inlines do
    local first = inlines[i]
    if first.t == "Str" and first.text:match("^%[") then
      local group, stop = pandoc.Inlines({}), nil
      for j = i, #inlines do
        local item = inlines[j]
        if item.t ~= "Str" and item.t ~= "Space" and item.t ~= "SoftBreak" then break end
        group:insert(item)
        if item.t == "Str" and item.text:match("%][%.,;:]?$") then stop = j; break end
      end
      if stop and #pandoc.utils.stringify(group) > 4 then
        local body = pandoc.write(pandoc.Pandoc({pandoc.Plain(group)}), "typst"):gsub("%s+$", "")
        out:insert(pandoc.RawInline("typst", '#text(fill: gris, style: "italic")[' .. body .. ']'))
        i = stop + 1
      else
        out:insert(first); i = i + 1
      end
    else
      out:insert(first); i = i + 1
    end
  end
  return out
end

local function module_breaks(doc)
  if module_level == 0 then
    return nil
  end
  local blocks = pandoc.Blocks({})
  local after_header = false
  for _, block in ipairs(doc.blocks) do
    if block.t == "Header" and block.level == module_level and not after_header then
      blocks:insert(pandoc.RawBlock("typst", "#pagebreak(weak: true)"))
    end
    blocks:insert(block)
    after_header = block.t == "Header"
  end
  doc.blocks = blocks
  return doc
end

local function source_number(header)
  local number = header.attributes["source-number"]
  if not number or not number:match("^%d[%d%.]*$") then return nil end
  local body = pandoc.write(pandoc.Pandoc({pandoc.Plain(header.content)}), "typst"):gsub("%s+$", "")
  -- El encabezado sigue siendo un heading real de Typst (índice y cabeceras),
  -- con la numeración de la PD original, sin insertar apartados vacíos.
  return pandoc.RawBlock("typst", '#heading(level: ' .. header.level
    .. ', numbering: (..n) => "' .. number .. '")[' .. body .. ']')
end

return {
  { Meta = read_meta },
  -- Los bloques anidados se resuelven de dentro hacia fuera: cada nivel suma
  -- su desplazamiento sobre el ya aplicado.
  { Div = shift_block },
  { RawInline = html_break, Header = module_title, Table = tables, Str = symbols },
  { Inlines = function(inlines) return pending_inlines(percent_nbsp(inlines)) end },
  { Para = letter_paragraph },
  { Pandoc = module_breaks },
  { Header = source_number },
}
