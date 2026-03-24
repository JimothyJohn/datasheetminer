//! Data models for datasheetminer products.
//!
//! Defines all product types (Motor, Drive, Gearhead, RobotArm),
//! shared types (ValueUnit, MinMaxUnit, ProductType), and the
//! Product tagged-union enum for polymorphic deserialization.

pub mod common;
pub mod datasheet;
pub mod drive;
pub mod error;
pub mod gearhead;
pub mod manufacturer;
pub mod motor;
pub mod product;
pub mod robot_arm;

pub use common::{MinMaxUnit, ProductType, ValueUnit};
pub use datasheet::Datasheet;
pub use drive::Drive;
pub use error::ModelError;
pub use gearhead::Gearhead;
pub use manufacturer::Manufacturer;
pub use motor::Motor;
pub use product::{Dimensions, Product, ProductBase};
pub use robot_arm::RobotArm;
