//! datasheetminer — unified CLI + web server for datasheet spec extraction.

mod cli;
mod server;

use clap::Parser;
use tracing_subscriber::EnvFilter;

use cli::{Cli, Commands};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new(&cli.log_level)),
        )
        .init();

    match cli.command {
        Commands::Scrape {
            product_type,
            url,
            pages,
            manufacturer,
            product_name,
            product_family,
            from_json,
            json_index,
            scrape_from_db,
            scrape_all,
            ref output,
            api_key,
            ref table,
        } => {
            cli::scrape::run(
                product_type.as_deref(),
                url.as_deref(),
                pages.as_deref(),
                manufacturer.as_deref(),
                product_name.as_deref(),
                product_family.as_deref(),
                from_json.as_ref(),
                json_index,
                scrape_from_db,
                scrape_all,
                output,
                api_key.as_deref(),
                table,
            )
            .await?;
        }
        Commands::Search {
            ref product_type,
            ref query,
            ref api,
            api_key,
            ref output,
            append,
            max_results,
        } => {
            cli::search::run(
                product_type,
                query,
                api,
                api_key.as_deref(),
                output,
                append,
                max_results,
            )
            .await?;
        }
        Commands::Push {
            ref file,
            ref table,
        } => {
            cli::push::run(file, table).await?;
        }
        Commands::Query {
            ref table,
            summary,
            list,
            get,
            ref product_type,
            limit,
            details,
        } => {
            cli::query::run(table, summary, list, get, product_type, limit, details).await?;
        }
        Commands::Delete {
            ref table,
            manufacturer,
            product_type,
            product_name,
            product_family,
            confirm,
            dry_run,
        } => {
            cli::delete::run(
                table,
                manufacturer.as_deref(),
                product_type.as_deref(),
                product_name.as_deref(),
                product_family.as_deref(),
                confirm,
                dry_run,
            )
            .await?;
        }
        Commands::Deduplicate {
            ref table,
            confirm,
            dry_run,
            json,
        } => {
            cli::deduplicate::run(table, confirm, dry_run, json).await?;
        }
        Commands::Serve {
            port,
            ref table,
            static_dir,
            cors_origin: _,
        } => {
            server::start(port, table, static_dir).await?;
        }
    }

    Ok(())
}
